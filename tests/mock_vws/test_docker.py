"""
Tests for running the mock server in Docker.
"""

from __future__ import annotations

import uuid
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

import docker  # type: ignore[import-untyped]
import pytest
import requests
from docker.errors import BuildError, NotFound  # type: ignore[import-untyped]
from docker.models.containers import Container  # type: ignore[import-untyped]
from docker.models.networks import Network  # type: ignore[import-untyped]
from mock_vws.database import VuforiaDatabase
from tenacity import retry
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from vws import VWS, CloudRecoService

if TYPE_CHECKING:
    import io
    from collections.abc import Iterator

    from docker.models.images import Image  # type: ignore[import-untyped]


# We do not cover this function because hitting particular branches depends on
# timing.
@retry(
    wait=wait_fixed(wait=0.5),
    stop=stop_after_delay(max_delay=10),
    retry=retry_if_exception_type(
        exception_types=(requests.exceptions.ConnectionError, ValueError),
    ),
    reraise=True,
)
def wait_for_flask_app_to_start(base_url: str) -> None:  # pragma: no cover
    """
    Wait for a server to start.

    Args:
        base_url: The base URL of the Flask app to wait for.
    """
    url = f"{base_url}/{uuid.uuid4().hex}"
    response = requests.get(url=url, timeout=30)
    if response.status_code not in {
        HTTPStatus.NOT_FOUND,
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
    }:
        error_message = f"Could not connect to {url}"
        raise ValueError(error_message)


@pytest.fixture(name="custom_bridge_network")
def fixture_custom_bridge_network() -> Iterator[Network]:
    """
    Yield a custom bridge network which containers can connect to.

    This also cleans up all containers connected to the network and the network
    after the test.

    Yields:
        A custom bridge network.
    """
    client = docker.from_env()
    try:
        network = client.networks.create(
            name="test-vws-bridge-" + uuid.uuid4().hex,
            driver="bridge",
        )
    except NotFound:
        # On Windows the "bridge" network driver is not available and we use
        # the "nat" driver instead.
        network = client.networks.create(
            name="test-vws-bridge-" + uuid.uuid4().hex,
            driver="nat",
        )

    assert isinstance(network, Network)
    try:
        yield network
    finally:
        network.reload()
        images_to_remove: set[Image] = set()
        for container in network.containers:
            assert isinstance(container, Container)
            network.disconnect(container=container)
            container.stop()
            container.remove(v=True, force=True)
            images_to_remove.add(container.image)

        # This does leave behind untagged images.
        for image in images_to_remove:
            image.remove(force=True)
        network.remove()


@pytest.mark.requires_docker_build()
def test_build_and_run(
    high_quality_image: io.BytesIO,
    custom_bridge_network: Network,
) -> None:
    """
    It is possible to build Docker images which combine to make a working mock
    application.
    """
    repository_root = Path(__file__).parent.parent.parent
    client = docker.from_env()

    dockerfile = repository_root / "src/mock_vws/_flask_server/Dockerfile"

    random = uuid.uuid4().hex
    target_manager_tag = f"vws-mock-target-manager:latest-{random}"
    vws_tag = f"vws-mock-vws:latest-{random}"
    vwq_tag = f"vws-mock-vwq:latest-{random}"

    try:
        target_manager_image, _ = client.images.build(
            path=str(repository_root),
            dockerfile=str(dockerfile),
            tag=target_manager_tag,
            target="target-manager",
            rm=True,
        )
    except BuildError as exc:
        full_log = "\n".join(
            [item["stream"] for item in exc.build_log if "stream" in item],
        )
        # If this assertion fails, it may be useful to look at the other
        # properties of ``exc``.
        if (
            "no matching manifest for windows/amd64" not in exc.msg
        ):  # pragma: no cover
            raise AssertionError(full_log) from exc
        reason = "We do not currently support using Windows containers."
        pytest.skip(reason)

    vwq_image, _ = client.images.build(
        path=str(repository_root),
        dockerfile=str(dockerfile),
        tag=vwq_tag,
        target="vwq",
        rm=True,
    )

    vws_image, _ = client.images.build(
        path=str(repository_root),
        dockerfile=str(dockerfile),
        tag=vws_tag,
        target="vws",
        rm=True,
    )

    database = VuforiaDatabase()
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

    assert isinstance(target_manager_container, Container)
    assert isinstance(vws_container, Container)
    assert isinstance(vwq_container, Container)
    for container in (target_manager_container, vws_container, vwq_container):
        container.reload()

    assert isinstance(target_manager_container.attrs, dict)
    target_manager_port_attrs = target_manager_container.attrs[
        "NetworkSettings"
    ]["Ports"]
    target_manager_port_attrs = target_manager_container.attrs[
        "NetworkSettings"
    ]["Ports"]
    task_manager_host_ip = target_manager_port_attrs["5000/tcp"][0]["HostIp"]
    task_manager_host_port = target_manager_port_attrs["5000/tcp"][0][
        "HostPort"
    ]

    assert isinstance(vws_container.attrs, dict)
    vws_port_attrs = vws_container.attrs["NetworkSettings"]["Ports"]
    vws_host_ip = vws_port_attrs["5000/tcp"][0]["HostIp"]
    vws_host_port = vws_port_attrs["5000/tcp"][0]["HostPort"]

    assert isinstance(vwq_container.attrs, dict)
    vwq_port_attrs = vwq_container.attrs["NetworkSettings"]["Ports"]
    vwq_host_ip = vwq_port_attrs["5000/tcp"][0]["HostIp"]
    vwq_host_port = vwq_port_attrs["5000/tcp"][0]["HostPort"]

    base_vws_url = f"http://{vws_host_ip}:{vws_host_port}"
    base_vwq_url = f"http://{vwq_host_ip}:{vwq_host_port}"
    base_task_manager_url = (
        f"http://{task_manager_host_ip}:{task_manager_host_port}"
    )

    for base_url in (base_vws_url, base_vwq_url, base_task_manager_url):
        wait_for_flask_app_to_start(base_url=base_url)

    response = requests.post(
        url=f"{base_task_manager_url}/databases",
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
