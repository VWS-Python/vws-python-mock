"""Tests for running the mock server in Docker.

Every other backend in the test suite runs the Flask applications of the
mock in one process, so no test there can tell state which lives in the
target manager service apart from state which lives in the VWS
application.
These tests run the applications as the Docker deployment runs them, in
separate containers, and so are the only tests which can.
"""

import datetime
import io
import json
import socket
import uuid
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from http import HTTPMethod, HTTPStatus
from zoneinfo import ZoneInfo

import docker
import pytest
import requests
from beartype import beartype
from docker.errors import BuildError, NotFound
from docker.models.containers import Container
from docker.models.images import Image
from docker.models.networks import Network
from tenacity import retry
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from vws import VWS, CloudRecoService, VuMarkService
from vws.exceptions.vws_exceptions import FailError, TooManyRequestsError
from vws.vumark_accept import VuMarkAccept
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.request_rate_limits import RequestRateLimit, RequestRateLimits
from mock_vws.target import VuMarkTarget

pytestmark = pytest.mark.requires_docker_build

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# The number of recognitions of a target which the reco counts report test
# seeds in the target manager service.
_CURRENT_MONTH_RECOS = 3


@beartype
@dataclass(frozen=True, kw_only=True)
class _MockDeployment:
    """The running mock containers and the URLs which reach them."""

    vws_container: Container
    base_vws_url: str
    base_vwq_url: str
    base_target_manager_url: str


@retry(
    wait=wait_fixed(wait=0.5),
    stop=stop_after_delay(max_delay=20),
    retry=retry_if_exception_type(
        exception_types=(requests.exceptions.ConnectionError, ValueError),
    ),
    reraise=True,
)
@beartype
def _poll_health_check(container: Container) -> None:
    """Poll a container until it reports a healthy status."""
    container.reload()
    health_status = container.attrs["State"]["Health"]["Status"]
    # In theory this might not be hit by coverage.
    # Let's keep it required by coverage for now.
    if health_status != "healthy":
        error_message = (
            f"Container {container.name} is not healthy: {health_status}"
        )
        raise ValueError(error_message)


@beartype
def wait_for_health_check(container: Container) -> None:
    """Wait for a container to pass its health check.

    On failure, augment the error with the container's logs and the
    Docker health check probe history so CI failures are easier to diagnose.
    """
    try:
        _poll_health_check(container=container)
    except ValueError as exc:  # pragma: no cover
        container.reload()
        logs = container.logs().decode(errors="replace")
        health_log = container.attrs["State"]["Health"].get("Log", [])
        probes = "\n".join(
            f"  exit={entry.get('ExitCode')!r} "
            f"start={entry.get('Start')!r} end={entry.get('End')!r}\n"
            f"  output={entry.get('Output')!r}"
            for entry in health_log
        )
        error_message = (
            f"{exc}\n"
            f"--- container logs ({container.name}) ---\n"
            f"{logs}\n"
            f"--- healthcheck probes ({container.name}) ---\n"
            f"{probes}"
        )
        raise ValueError(error_message) from exc


@retry(
    wait=wait_fixed(wait=0.5),
    stop=stop_after_delay(max_delay=60),
    retry=retry_if_exception_type(exception_types=(ValueError,)),
    reraise=True,
)
@beartype
def _wait_for_model_target_dataset_done(
    *,
    base_vws_url: str,
    dataset_uuid: str,
    access_token: str,
) -> None:
    """Poll a Model Target dataset until it finishes processing."""
    response = requests.get(
        url=f"{base_vws_url}/modeltargets/datasets/{dataset_uuid}/status",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    assert response.status_code == HTTPStatus.OK
    status = response.json()["status"]
    if status != "done":
        error_message = f"Dataset {dataset_uuid} status is {status!r}."
        raise ValueError(error_message)


@retry(
    wait=wait_fixed(wait=0.5),
    stop=stop_after_delay(max_delay=60),
    retry=retry_if_exception_type(exception_types=(ValueError,)),
    reraise=True,
)
@beartype
def _wait_for_reco_counts_report(*, presigned_url: str) -> str:
    """Poll a reco counts report until it is generated.

    Returns:
        The content of the generated report.
    """
    response = requests.get(url=presigned_url, timeout=30)
    if response.status_code != HTTPStatus.OK:
        error_message = (
            f"Report at {presigned_url} is not ready: {response.status_code}."
        )
        raise ValueError(error_message)
    return response.text


@beartype
def _current_month() -> str:
    """Return the current month in the ``YYYY-mm`` form.

    Returns:
        The month which a reco counts report is requested for.
    """
    now = datetime.datetime.now(tz=ZoneInfo(key="UTC"))
    return now.strftime(format="%Y-%m")


@beartype
def _free_port() -> int:
    """Return a port which is free on the host.

    The VWS container publishes to a known port so that the base URL which
    it builds report download URLs from is known before it starts, and so
    that the URLs which reach it survive a restart of the container.

    Returns:
        A port which nothing was listening on when this was called.
    """
    with socket.socket(
        family=socket.AF_INET,
        type=socket.SOCK_STREAM,
    ) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@beartype
def _published_base_url(*, container: Container) -> str:
    """Return the host-reachable base URL of a container."""
    container.reload()
    port_attrs = container.attrs["NetworkSettings"]["Ports"]
    host_ip = port_attrs["5000/tcp"][0]["HostIp"]
    host_port = port_attrs["5000/tcp"][0]["HostPort"]
    return f"http://{host_ip}:{host_port}"


@beartype
def _create_cloud_database(
    *,
    deployment: _MockDeployment,
    database: CloudDatabase,
) -> None:
    """Create a cloud database in the target manager container."""
    response = requests.post(
        url=f"{deployment.base_target_manager_url}/cloud_databases",
        json=database.to_dict(),
        timeout=30,
    )
    assert response.status_code == HTTPStatus.CREATED


@beartype
def _vws_client(
    *,
    deployment: _MockDeployment,
    database: CloudDatabase,
) -> VWS:
    """Return a VWS client for a database, pointed at the VWS
    container.
    """
    return VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
        base_vws_url=deployment.base_vws_url,
    )


@pytest.fixture(name="custom_bridge_network", scope="module")
def fixture_custom_bridge_network() -> Iterator[Network]:
    """Yield a custom bridge network which containers can connect to.

    This also cleans up all containers connected to the network and the network
    after the tests.

    Yields:
        A custom bridge network.
    """
    client = docker.from_env()
    name = "test-vws-bridge-" + uuid.uuid4().hex
    try:
        network = client.networks.create(name=name, driver="bridge")
    except NotFound:
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


@beartype
def _build_image(*, repository_root: str, tag: str, target: str) -> Image:
    """Build one stage of the ``Dockerfile`` of the mock.

    Returns:
        The built image.
    """
    client = docker.from_env()
    dockerfile = f"{repository_root}/src/mock_vws/_flask_server/Dockerfile"
    image, _ = client.images.build(
        path=repository_root,
        dockerfile=dockerfile,
        tag=tag,
        target=target,
        rm=True,
    )
    return image


@pytest.fixture(name="mock_deployment", scope="module")
def fixture_mock_deployment(
    *,
    custom_bridge_network: Network,
    request: pytest.FixtureRequest,
) -> _MockDeployment:
    """Build the mock's images and run them as the Docker deployment does.

    The images are built and the containers are run once for all tests in
    this module, because building the images is the slowest thing these
    tests do.

    Returns:
        The running deployment.
    """
    repository_root = str(object=request.config.rootpath)
    client = docker.from_env()
    random = uuid.uuid4().hex

    try:
        target_manager_image = _build_image(
            repository_root=repository_root,
            tag=f"vws-mock-target-manager:latest-{random}",
            target="target-manager",
        )
    except BuildError as exc:
        full_log = "\n".join(
            [item["stream"] for item in exc.build_log if "stream" in item],
        )
        windows_message_substrings = (
            "no matching manifest for windows/amd64",
            "no matching manifest for windows(10.0.26100)/amd64",
        )
        # If this assertion fails, it may be useful to look at the other
        # properties of ``exc``.
        is_windows_container_error = any(
            windows_message_substring in exc.msg
            for windows_message_substring in windows_message_substrings
        )
        assert is_windows_container_error, full_log
        pytest.skip(
            reason="We do not currently support using Windows containers."
        )

    vwq_image = _build_image(
        repository_root=repository_root,
        tag=f"vws-mock-vwq:latest-{random}",
        target="vwq",
    )
    vws_image = _build_image(
        repository_root=repository_root,
        tag=f"vws-mock-vws:latest-{random}",
        target="vws",
    )

    target_manager_container_name = "vws-mock-target-manager-" + random
    target_manager_internal_base_url = (
        f"http://{target_manager_container_name}:5000"
    )
    vws_host_port = _free_port()
    base_vws_url = f"http://127.0.0.1:{vws_host_port}"

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
        ports={"5000/tcp": ("127.0.0.1", vws_host_port)},
        network=custom_bridge_network.name,
        environment={
            "TARGET_MANAGER_BASE_URL": target_manager_internal_base_url,
            # Report download URLs are built from this, so the URLs which
            # the VWS container gives out reach it from the host.
            "VWS_BASE_URL": base_vws_url,
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

    return _MockDeployment(
        vws_container=vws_container,
        base_vws_url=base_vws_url,
        base_vwq_url=_published_base_url(container=vwq_container),
        base_target_manager_url=_published_base_url(
            container=target_manager_container,
        ),
    )


def test_add_target_and_query(
    *,
    high_quality_image: io.BytesIO,
    mock_deployment: _MockDeployment,
) -> None:
    """A target added through the VWS container is matched by a query
    made against the query container.
    """
    database = CloudDatabase()
    _create_cloud_database(deployment=mock_deployment, database=database)
    vws_client = _vws_client(
        deployment=mock_deployment,
        database=database,
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
        base_vwq_url=mock_deployment.base_vwq_url,
    )

    matching_targets = cloud_reco_client.query(image=high_quality_image)

    assert matching_targets[0].target_id == target_id


def test_model_target_dataset_survives_vws_restart(
    *,
    mock_deployment: _MockDeployment,
) -> None:
    """A Model Target dataset is created in one request and downloaded in
    another, and survives a restart of the VWS container.

    Datasets are stored in the target manager container, so a restart of
    the VWS container must not lose them.
    """
    base_vws_url = mock_deployment.base_vws_url
    oauth_response = requests.post(
        url=f"{base_vws_url}/oauth2/token",
        auth=("client-id", "client-secret"),
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    assert oauth_response.status_code == HTTPStatus.OK
    access_token = oauth_response.json()["access_token"]

    dataset_request = {
        "name": "example-dataset",
        "targetSdk": "10.18",
        "models": [
            {
                "name": "model-name",
                "cadDataUrl": "https://example.com/model.glb",
                "views": [
                    {
                        "name": "view-name",
                        "guideViewPosition": {
                            "translation": [0, 0, 5],
                            "rotation": [0, 0, 0, 1],
                        },
                    },
                ],
            },
        ],
    }
    create_dataset_response = requests.post(
        url=f"{base_vws_url}/modeltargets/datasets",
        headers={"Authorization": f"Bearer {access_token}"},
        json=dataset_request,
        timeout=30,
    )
    assert create_dataset_response.status_code == HTTPStatus.CREATED
    dataset_uuid = create_dataset_response.json()["uuid"]

    _wait_for_model_target_dataset_done(
        base_vws_url=base_vws_url,
        dataset_uuid=dataset_uuid,
        access_token=access_token,
    )

    mock_deployment.vws_container.restart()
    wait_for_health_check(container=mock_deployment.vws_container)

    status_response = requests.get(
        url=f"{base_vws_url}/modeltargets/datasets/{dataset_uuid}/status",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    assert status_response.status_code == HTTPStatus.OK
    assert status_response.json()["status"] == "done"

    download_response = requests.get(
        url=f"{base_vws_url}/modeltargets/datasets/{dataset_uuid}/dataset",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    assert download_response.status_code == HTTPStatus.OK
    with zipfile.ZipFile(
        file=io.BytesIO(initial_bytes=download_response.content),
    ) as downloaded_zip:
        assert downloaded_zip.namelist() == ["MTDataset.dat", "MTDataset.xml"]


def test_reco_counts_report_round_trip(
    *,
    high_quality_image: io.BytesIO,
    mock_deployment: _MockDeployment,
) -> None:
    """A reco counts report is requested from the VWS container and then
    downloaded from the URL which that request gives.

    The recognition counts in the report come from the target manager
    container, while the report itself is served by the VWS container,
    which stands in for the cloud storage which real Vuforia serves a
    report from.
    """
    database = CloudDatabase()
    _create_cloud_database(deployment=mock_deployment, database=database)
    vws_client = _vws_client(deployment=mock_deployment, database=database)
    target_id = vws_client.add_target(
        name="example",
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=None,
    )
    vws_client.wait_for_target_processed(target_id=target_id)

    recognition_counts_response = requests.post(
        url=(
            f"{mock_deployment.base_target_manager_url}/cloud_databases/"
            f"{database.database_name}/targets/{target_id}/"
            "recognition_counts"
        ),
        json={"current_month_recos": _CURRENT_MONTH_RECOS},
        timeout=30,
    )
    assert recognition_counts_response.status_code == HTTPStatus.OK

    request_path = (
        f"/imagetargets/databases/{database.database_id}/reports/recoCounts"
    )
    content_type = "application/json"
    content = json.dumps(obj={"month": _current_month()}).encode(
        encoding="utf-8",
    )
    date = rfc_1123_date()
    authorization_string = authorization_header(
        access_key=database.server_access_key,
        secret_key=database.server_secret_key,
        method=HTTPMethod.POST,
        content=content,
        content_type=content_type,
        date=date,
        request_path=request_path,
    )
    report_response = requests.post(
        url=mock_deployment.base_vws_url + request_path,
        headers={
            "Authorization": authorization_string,
            "Content-Length": str(object=len(content)),
            "Content-Type": content_type,
            "Date": date,
        },
        data=content,
        timeout=30,
    )

    assert report_response.status_code == HTTPStatus.OK
    report_json = report_response.json()
    assert report_json["result_code"] == "Success"
    presigned_url = report_json["presigned_url"]
    # The download URL is built from the ``VWS_BASE_URL`` of the VWS
    # container, so it reaches that container.
    assert presigned_url.startswith(mock_deployment.base_vws_url)

    report_content = _wait_for_reco_counts_report(presigned_url=presigned_url)

    assert report_content == (
        f"target_id,reco_count\r\n{target_id},{_CURRENT_MONTH_RECOS}\r\n"
    )


def test_vumark_instance_generation(
    *,
    mock_deployment: _MockDeployment,
) -> None:
    """A VuMark instance is generated from a VuMark target which was
    created in the target manager container.
    """
    vumark_target = VuMarkTarget(name="example-vumark-target")
    vumark_database = VuMarkDatabase()
    create_database_response = requests.post(
        url=f"{mock_deployment.base_target_manager_url}/vumark_databases",
        json=vumark_database.to_dict(),
        timeout=30,
    )
    assert create_database_response.status_code == HTTPStatus.CREATED
    create_target_response = requests.post(
        url=(
            f"{mock_deployment.base_target_manager_url}/vumark_databases/"
            f"{vumark_database.database_name}/vumark_targets"
        ),
        json=vumark_target.to_dict(),
        timeout=30,
    )
    assert create_target_response.status_code == HTTPStatus.CREATED

    vumark_client = VuMarkService(
        server_access_key=vumark_database.server_access_key,
        server_secret_key=vumark_database.server_secret_key,
        base_vws_url=mock_deployment.base_vws_url,
    )

    instance = vumark_client.generate_vumark_instance(
        target_id=vumark_target.target_id,
        instance_id="example-instance",
        accept=VuMarkAccept.PNG,
    )

    assert instance.startswith(_PNG_SIGNATURE)


def test_request_rate_limit(*, mock_deployment: _MockDeployment) -> None:
    """The VWS container enforces the request rate limits of a database
    which the target manager container holds.

    Request rate limit history is the one piece of state which each VWS
    application instance keeps for itself, so it is lost when the
    container restarts.
    """
    database = CloudDatabase(
        request_rate_limits=RequestRateLimits(
            list_targets=RequestRateLimit(
                max_requests=1,
                window_seconds=60.0,
            ),
        ),
    )
    _create_cloud_database(deployment=mock_deployment, database=database)
    vws_client = _vws_client(deployment=mock_deployment, database=database)

    vws_client.list_targets()

    with pytest.raises(expected_exception=TooManyRequestsError):
        vws_client.list_targets()

    # Other endpoints are not limited.
    vws_client.get_database_summary_report()

    mock_deployment.vws_container.restart()
    wait_for_health_check(container=mock_deployment.vws_container)

    vws_client.list_targets()


def test_deleted_database(*, mock_deployment: _MockDeployment) -> None:
    """The VWS container rejects the credentials of a database which was
    deleted from the target manager container.

    The keys of a deleted database match no database, which the VWS
    application treats as it treats any unknown server access key.
    """
    database = CloudDatabase()
    _create_cloud_database(deployment=mock_deployment, database=database)
    vws_client = _vws_client(deployment=mock_deployment, database=database)

    vws_client.list_targets()

    delete_response = requests.delete(
        url=(
            f"{mock_deployment.base_target_manager_url}/cloud_databases/"
            f"{database.database_name}"
        ),
        timeout=30,
    )
    assert delete_response.status_code == HTTPStatus.OK

    with pytest.raises(expected_exception=FailError) as exc:
        vws_client.list_targets()

    assert exc.value.response.status_code == HTTPStatus.BAD_REQUEST
