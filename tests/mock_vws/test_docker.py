"""
Tests for running the mock server in Docker.
"""

from __future__ import annotations

import time
import uuid
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

import docker
import pytest
import requests
from docker.errors import BuildError, NotFound
from docker.models.containers import Container
from docker.models.networks import Network
from mock_vws.database import VuforiaDatabase
from vws import VWS, CloudRecoService

if TYPE_CHECKING:
    import io
    from collections.abc import Iterator


# We do not cover this function because hitting particular branches depends on
# timing.
def wait_for_flask_app_to_start(base_url: str) -> None:  # pragma: no cover
    """
    Wait for a server to start.

    Args:
        base_url: The base URL of the Flask app to wait for.
    """
    max_attempts = 10
    sleep_seconds = 0.5
    url = f"{base_url}/{uuid.uuid4().hex}"
    for _ in range(max_attempts):
        try:
            response = requests.get(url, timeout=30)
        except requests.exceptions.ConnectionError:
            time.sleep(sleep_seconds)
        else:
            if response.status_code in {
                HTTPStatus.NOT_FOUND,
                HTTPStatus.UNAUTHORIZED,
                HTTPStatus.FORBIDDEN,
            }:
                return
    error_message = (
        f"Could not connect to {url} after "
        f"{max_attempts * sleep_seconds} seconds."
    )
    raise RuntimeError(error_message)


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
        for container in network.containers:
            network.disconnect(container=container)
            container.stop()
            container.remove()
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

    dockerfile_dir = repository_root / "src/mock_vws/_flask_server/dockerfiles"
    target_manager_dockerfile = (
        dockerfile_dir / "target_manager" / "Dockerfile"
    )
    vws_dockerfile = dockerfile_dir / "vws" / "Dockerfile"
    vwq_dockerfile = dockerfile_dir / "vwq" / "Dockerfile"

    random = uuid.uuid4().hex
    target_manager_tag = f"vws-mock-target-manager:latest-{random}"
    vws_tag = f"vws-mock-vws:latest-{random}"
    vwq_tag = f"vws-mock-vwq:latest-{random}"

    try:
        target_manager_build_result = client.images.build(
            path=str(repository_root),
            dockerfile=str(target_manager_dockerfile),
            tag=target_manager_tag,
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

    assert isinstance(target_manager_build_result, tuple)
    target_manager_image, _ = target_manager_build_result

    vws_build_result = client.images.build(
        path=str(repository_root),
        dockerfile=str(vws_dockerfile),
        tag=vws_tag,
    )
    assert isinstance(vws_build_result, tuple)
    vws_image, _ = vws_build_result
    vwq_build_result = client.images.build(
        path=str(repository_root),
        dockerfile=str(vwq_dockerfile),
        tag=vwq_tag,
    )
    assert isinstance(vwq_build_result, tuple)
    vwq_image, _ = vwq_build_result

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
