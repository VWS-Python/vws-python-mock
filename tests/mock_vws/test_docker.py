"""
Tests for running the mock server in Docker.
"""

import io
import os
import uuid
from http import HTTPStatus
from pathlib import Path
from typing import Iterator

import docker
import pytest
import requests
from docker.models.networks import Network
from vws import VWS, CloudRecoService

from mock_vws.database import VuforiaDatabase


@pytest.fixture(name='custom_bridge_network')
def fixture_custom_bridge_network() -> Iterator[Network]:
    """
    Yield a custom bridge network which containers can connect to.
    """
    client = docker.from_env()
    try:
        network = client.networks.create(
            name='test-vws-bridge-' + uuid.uuid4().hex,
            driver='bridge',
        )
    except docker.errors.NotFound:
        # On Windows the "bridge" network driver is not available and we use
        # the "nat" driver instead.
        network = client.networks.create(
            name='test-vws-bridge-' + uuid.uuid4().hex,
            driver='nat',
        )
    try:
        yield network
    finally:
        network.remove()


@pytest.mark.skipif(
    os.environ.get('SKIP_DOCKER_BUILD_TESTS') == '1',
    reason='Docker test skipped because environment variable was set.',
)
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

    dockerfile_dir = repository_root / 'src/mock_vws/_flask_server/dockerfiles'
    target_manager_dockerfile = (
        dockerfile_dir / 'target_manager' / 'Dockerfile'
    )
    vws_dockerfile = dockerfile_dir / 'vws' / 'Dockerfile'
    vwq_dockerfile = dockerfile_dir / 'vwq' / 'Dockerfile'

    random = uuid.uuid4().hex
    target_manager_tag = 'vws-mock-target-manager:latest-' + random
    vws_tag = 'vws-mock-vws:latest-' + random
    vwq_tag = 'vws-mock-vwq:latest-' + random

    try:
        target_manager_image, _ = client.images.build(
            path=str(repository_root),
            dockerfile=str(target_manager_dockerfile),
            tag=target_manager_tag,
        )
    except docker.errors.BuildError as exc:
        full_log = '\n'.join(
            [item['stream'] for item in exc.build_log if 'stream' in item],
        )
        # If this assertion fails, it may be useful to look at the other
        # properties of ``exc``.
        assert 'no matching manifest for windows/amd64' in exc.msg, full_log
        reason = 'We do not currently support using Windows containers.'
        pytest.skip(reason)

    vws_image, _ = client.images.build(
        path=str(repository_root),
        dockerfile=str(vws_dockerfile),
        tag=vws_tag,
    )
    vwq_image, _ = client.images.build(
        path=str(repository_root),
        dockerfile=str(vwq_dockerfile),
        tag=vwq_tag,
    )

    database = VuforiaDatabase()
    target_manager_container_name = 'vws-mock-target-manager-' + random
    target_manager_base_url = f'http://{target_manager_container_name}:5000'

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
        name='vws-mock-vws-' + random,
        publish_all_ports=True,
        network=custom_bridge_network.name,
        environment={'TARGET_MANAGER_BASE_URL': target_manager_base_url},
    )
    vwq_container = client.containers.run(
        image=vwq_image,
        detach=True,
        name='vws-mock-vwq-' + random,
        publish_all_ports=True,
        network=custom_bridge_network.name,
        environment={'TARGET_MANAGER_BASE_URL': target_manager_base_url},
    )

    target_manager_container.reload()
    target_manager_port_attrs = target_manager_container.attrs[
        'NetworkSettings'
    ]['Ports']
    target_manager_host_ip = target_manager_port_attrs['5000/tcp'][0]['HostIp']
    target_manager_host_port = target_manager_port_attrs['5000/tcp'][0][
        'HostPort'
    ]

    vws_container.reload()
    vws_port_attrs = vws_container.attrs['NetworkSettings']['Ports']
    vws_host_ip = vws_port_attrs['5000/tcp'][0]['HostIp']
    vws_host_port = vws_port_attrs['5000/tcp'][0]['HostPort']

    vwq_container.reload()
    vwq_port_attrs = vwq_container.attrs['NetworkSettings']['Ports']
    vwq_host_ip = vwq_port_attrs['5000/tcp'][0]['HostIp']
    vwq_host_port = vwq_port_attrs['5000/tcp'][0]['HostPort']

    target_manager_host_url = (
        f'http://{target_manager_host_ip}:{target_manager_host_port}'
    )
    response = requests.post(
        url=f'{target_manager_host_url}/databases',
        json=database.to_dict(),
    )

    assert response.status_code == HTTPStatus.CREATED

    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
        base_vws_url=f'http://{vws_host_ip}:{vws_host_port}',
    )

    target_id = vws_client.add_target(
        name='example',
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=target_id)

    cloud_reco_client = CloudRecoService(
        client_access_key=database.client_access_key,
        client_secret_key=database.client_secret_key,
        base_vwq_url=f'http://{vwq_host_ip}:{vwq_host_port}',
    )

    matching_targets = cloud_reco_client.query(image=high_quality_image)

    for container in (target_manager_container, vws_container, vwq_container):
        container.stop()
        container.remove()

    assert matching_targets[0].target_id == target_id
