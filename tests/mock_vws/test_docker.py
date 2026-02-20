"""Tests for running the mock server in Docker."""

import io
import uuid
from collections.abc import Iterable, Iterator
from http import HTTPStatus
from typing import TYPE_CHECKING

import docker
import pytest
import requests
from beartype import beartype
from docker.errors import BuildError, NotFound
from docker.models.containers import Container
from docker.models.networks import Network
from tenacity import retry
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from vws import VWS, CloudRecoService

from mock_vws.database import CloudDatabase

if TYPE_CHECKING:
    from docker.models.images import Image


@retry(
    wait=wait_fixed(wait=0.5),
    stop=stop_after_delay(max_delay=20),
    retry=retry_if_exception_type(
        exception_types=(requests.exceptions.ConnectionError, ValueError),
    ),
    reraise=True,
)
@beartype
def wait_for_health_check(container: Container) -> None:
    """Wait for a container to pass its health check."""
    container.reload()
    health_status = container.attrs["State"]["Health"]["Status"]
    # In theory this might not be hit by coverage.
    # Let's keep it required by coverage for now.
    if health_status != "healthy":
        error_message = (
            f"Container {container.name} is not healthy: {health_status}"
        )
        raise ValueError(error_message)


@pytest.fixture(name="custom_bridge_network")
def fixture_custom_bridge_network() -> Iterator[Network]:
    """Yield a custom bridge network which containers can connect to.

    This also cleans up all containers connected to the network and the network
    after the test.

    Yields:
        A custom bridge network.
    """
    client = docker.from_env()
    name = "test-vws-bridge-" + uuid.uuid4().hex
    try:
        network = client.networks.create(name=name, driver="bridge")
    # We skip coverage here because combining Windows and Linux coverage
    # is challenging.
    except NotFound:  # pragma: no cover
        # On Windows the "bridge" network driver is not available and we use
        # the "nat" driver instead.
        network = client.networks.create(name=name, driver="nat")

    try:
        yield network
    finally:
        network.reload()
        images_to_remove: Iterable[Image] = set()
        for container in network.containers:
            network.disconnect(container=container)
            container.stop()
            container.remove(v=True, force=True)
            assert container.image is not None
            images_to_remove = {*images_to_remove, container.image}

        # This does leave behind untagged images.
        for image in images_to_remove:
            image.remove(force=True)
        network.remove()


@pytest.mark.requires_docker_build
def test_build_and_run(
    high_quality_image: io.BytesIO,
    custom_bridge_network: Network,
    request: pytest.FixtureRequest,
) -> None:
    """
    It is possible to build Docker images which combine to make a
    working mock
    application.
    """
    repository_root = request.config.rootpath
    client = docker.from_env()

    dockerfile = repository_root / "src/mock_vws/_flask_server/Dockerfile"

    random = uuid.uuid4().hex
    target_manager_tag = f"vws-mock-target-manager:latest-{random}"
    vws_tag = f"vws-mock-vws:latest-{random}"
    vwq_tag = f"vws-mock-vwq:latest-{random}"

    try:
        target_manager_image, _ = client.images.build(
            path=str(object=repository_root),
            dockerfile=str(object=dockerfile),
            tag=target_manager_tag,
            target="target-manager",
            rm=True,
        )
    # We skip coverage here because combining Windows and Linux coverage
    # is challenging.
    except BuildError as exc:  # pragma: no cover
        full_log = "\n".join(
            [item["stream"] for item in exc.build_log if "stream" in item],
        )
        windows_message_substrings = (
            "no matching manifest for windows/amd64",
            "no matching manifest for windows(10.0.26100)/amd64",
        )
        # If this assertion fails, it may be useful to look at the other
        # properties of ``exc``.
        if not any(
            windows_message_substring in exc.msg
            for windows_message_substring in windows_message_substrings
        ):
            raise AssertionError(full_log) from exc
        pytest.skip(
            reason="We do not currently support using Windows containers."
        )

    vwq_image, _ = client.images.build(
        path=str(object=repository_root),
        dockerfile=str(object=dockerfile),
        tag=vwq_tag,
        target="vwq",
        rm=True,
    )

    vws_image, _ = client.images.build(
        path=str(object=repository_root),
        dockerfile=str(object=dockerfile),
        tag=vws_tag,
        target="vws",
        rm=True,
    )

    database = CloudDatabase()
    target_manager_container_name = "vws-mock-target-manager-" + random
    target_manager_internal_base_url = (
        f"http://{target_manager_container_name}:5000"
    )

    target_manager_container = client.containers.run(
        image=target_manager_image,
        detach=True,
        name=target_manager_container_name,
        publish_all_ports=True,
        network=custom_bridge_network.name,
    )
    vws_container = client.containers.run(
        image=vws_image,
        detach=True,
        name="vws-mock-vws-" + random,
        publish_all_ports=True,
        network=custom_bridge_network.name,
        environment={
            "TARGET_MANAGER_BASE_URL": target_manager_internal_base_url,
        },
    )
    vwq_container = client.containers.run(
        image=vwq_image,
        detach=True,
        name="vws-mock-vwq-" + random,
        publish_all_ports=True,
        network=custom_bridge_network.name,
        environment={
            "TARGET_MANAGER_BASE_URL": target_manager_internal_base_url,
        },
    )

    for container in (target_manager_container, vws_container, vwq_container):
        wait_for_health_check(container=container)
        container.reload()

    target_manager_port_attrs = target_manager_container.attrs[
        "NetworkSettings"
    ]["Ports"]
    target_manager_port_attrs = target_manager_container.attrs[
        "NetworkSettings"
    ]["Ports"]
    target_manager_host_ip = target_manager_port_attrs["5000/tcp"][0]["HostIp"]
    target_manager_host_port = target_manager_port_attrs["5000/tcp"][0][
        "HostPort"
    ]

    vws_port_attrs = vws_container.attrs["NetworkSettings"]["Ports"]
    vws_host_ip = vws_port_attrs["5000/tcp"][0]["HostIp"]
    vws_host_port = vws_port_attrs["5000/tcp"][0]["HostPort"]

    vwq_port_attrs = vwq_container.attrs["NetworkSettings"]["Ports"]
    vwq_host_ip = vwq_port_attrs["5000/tcp"][0]["HostIp"]
    vwq_host_port = vwq_port_attrs["5000/tcp"][0]["HostPort"]

    base_vws_url = f"http://{vws_host_ip}:{vws_host_port}"
    base_vwq_url = f"http://{vwq_host_ip}:{vwq_host_port}"
    base_target_manager_url = (
        f"http://{target_manager_host_ip}:{target_manager_host_port}"
    )

    response = requests.post(
        url=f"{base_target_manager_url}/cloud_databases",
        json=database.to_dict(),
        timeout=30,
    )

    assert response.status_code == HTTPStatus.CREATED

    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
        base_vws_url=base_vws_url,
    )

    target_id = vws_client.add_target(
        name="example",
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=target_id)

    cloud_reco_client = CloudRecoService(
        client_access_key=database.client_access_key,
        client_secret_key=database.client_secret_key,
        base_vwq_url=base_vwq_url,
    )

    matching_targets = cloud_reco_client.query(image=high_quality_image)

    assert matching_targets[0].target_id == target_id
