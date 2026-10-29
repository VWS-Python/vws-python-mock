"""Tests for running the mock server in Docker.

Every other backend in the test suite runs the Flask applications of the
mock in one process, so no test there can tell state which lives in the
target manager service apart from state which lives in the VWS
application.
These tests run the applications as the Docker deployment runs them, in
separate containers, and so are the only tests which can.
"""

import datetime as dt
import io
import json
import zipfile
from http import HTTPMethod, HTTPStatus
from zoneinfo import ZoneInfo

import pytest
import requests
from beartype import beartype
from pydantic import TypeAdapter
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

from .deployment import (
    MockDeployment,
    fixture_mock_deployment,
    wait_for_health_check,
)

__all__ = ["fixture_mock_deployment"]

pytestmark = pytest.mark.requires_docker_build

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# The number of recognitions of a target which the reco counts report test
# seeds in the target manager service.
_CURRENT_MONTH_RECOS = 3


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
    response_json = TypeAdapter(type=dict[str, object]).validate_python(
        response.json(),
    )
    status: object = response_json["status"]
    assert isinstance(status, str)
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
    now = dt.datetime.now(tz=ZoneInfo(key="UTC"))
    return now.strftime(format="%Y-%m")


@beartype
def _create_cloud_database(
    *,
    deployment: MockDeployment,
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
    deployment: MockDeployment,
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


def test_add_target_and_query(
    *,
    high_quality_image: io.BytesIO,
    mock_deployment: MockDeployment,
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
    mock_deployment: MockDeployment,
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
    oauth_response_json = TypeAdapter(type=dict[str, object]).validate_python(
        oauth_response.json(),
    )
    access_token: object = oauth_response_json["access_token"]
    assert isinstance(access_token, str)

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
    create_response_json = TypeAdapter(type=dict[str, object]).validate_python(
        create_dataset_response.json(),
    )
    dataset_uuid: object = create_response_json["uuid"]
    assert isinstance(dataset_uuid, str)

    _wait_for_model_target_dataset_done(
        base_vws_url=base_vws_url,
        dataset_uuid=dataset_uuid,
        access_token=access_token,
    )

    mock_deployment.vws_container.restart()
    wait_for_health_check(
        container=mock_deployment.vws_container,
        base_url=mock_deployment.base_vws_url,
    )

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
    mock_deployment: MockDeployment,
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
    presigned_url: object = report_json["presigned_url"]
    assert isinstance(presigned_url, str)
    # The download URL is built from the ``VWS_BASE_URL`` of the VWS
    # container, so it reaches that container.
    assert presigned_url.startswith(mock_deployment.base_vws_url)

    report_content = _wait_for_reco_counts_report(presigned_url=presigned_url)

    assert report_content == (
        f"target_id,reco_count\r\n{target_id},{_CURRENT_MONTH_RECOS}\r\n"
    )


def test_vumark_instance_generation(
    *,
    mock_deployment: MockDeployment,
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


def test_request_rate_limit(*, mock_deployment: MockDeployment) -> None:
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

    _targets = vws_client.list_targets()

    with pytest.raises(expected_exception=TooManyRequestsError):
        _targets = vws_client.list_targets()

    # Other endpoints are not limited.
    _summary = vws_client.get_database_summary_report()

    mock_deployment.vws_container.restart()
    wait_for_health_check(
        container=mock_deployment.vws_container,
        base_url=mock_deployment.base_vws_url,
    )

    _targets = vws_client.list_targets()


def test_deleted_database(*, mock_deployment: MockDeployment) -> None:
    """The VWS container rejects the credentials of a database which was
    deleted from the target manager container.

    The keys of a deleted database match no database, which the VWS
    application treats as it treats any unknown server access key.
    """
    database = CloudDatabase()
    _create_cloud_database(deployment=mock_deployment, database=database)
    vws_client = _vws_client(deployment=mock_deployment, database=database)

    _ = vws_client.list_targets()

    delete_response = requests.delete(
        url=(
            f"{mock_deployment.base_target_manager_url}/cloud_databases/"
            f"{database.database_name}"
        ),
        timeout=30,
    )
    assert delete_response.status_code == HTTPStatus.OK

    with pytest.raises(expected_exception=FailError) as exc:
        _ = vws_client.list_targets()

    assert exc.value.response.status_code == HTTPStatus.BAD_REQUEST
