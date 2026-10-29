"""Flask transport setup and controls for the contract-test adapter."""

import gzip
import os
from collections.abc import Generator
from http import HTTPMethod

import pytest
import requests
import responses
from beartype import beartype
from requests_mock_flask import add_flask_app_to_mock

from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.states import States
from vws_mock_contract_tests.fixtures.credentials import (
    InactiveVuMarkCloudDatabase,
    VuMarkCloudDatabase,
)
from vws_mock_contract_tests.utils.unrouted_requests import UnroutedResponse
from vws_mock_server.target_manager import TARGET_MANAGER_FLASK_APP
from vws_mock_server.vwq import CLOUDRECO_FLASK_APP
from vws_mock_server.vws import VWS_FLASK_APP
from vws_mock_test_backends.mock_databases import create_vumark_database


@beartype
def enable_flask_in_process(
    *,
    working_database: CloudDatabase,
    inactive_cloud_database: CloudDatabase,
    vumark_vuforia_database: VuMarkCloudDatabase,
    inactive_vumark_database: InactiveVuMarkCloudDatabase,
    monkeypatch: pytest.MonkeyPatch,
    base_vws_url: str,
    base_vwq_url: str,
) -> Generator[None]:
    """Test against the Flask applications of the mock, in this process.

    This exercises the handlers of the Flask applications which the
    Docker deployment runs, but not the deployment itself: all three
    applications are served from one process, so state which the
    deployment keeps in separate containers is shared here.
    ``tests/mock_vws/test_docker.py`` covers the container split.
    """
    # We set ``wsgi.input_terminated`` to ``True`` so that when going through
    # ``requests`` in our tests, the Flask applications
    # have the given ``Content-Length`` headers and the given data in
    # ``request.headers`` and ``request.data``.
    #
    # We do not set these in the Flask application itself.
    # This is because when running the Flask application, if this is set,
    # reading ``request.data`` hangs.
    #
    # Therefore, when running the real Flask application, the behavior is not
    # the same as the real Vuforia.
    # This is documented as a difference in the documentation for this package.
    VWS_FLASK_APP.config["VWS_MOCK_TERMINATE_WSGI_INPUT"] = True
    CLOUDRECO_FLASK_APP.config["VWS_MOCK_TERMINATE_WSGI_INPUT"] = True

    monkeypatch.setenv(name="VWS_BASE_URL", value=base_vws_url)
    target_manager_base_url = "http://example.com"
    monkeypatch.setenv(
        name="TARGET_MANAGER_BASE_URL",
        value=target_manager_base_url,
    )
    vumark_database = create_vumark_database(
        vumark_vuforia_database=vumark_vuforia_database,
    )
    inactive_vumark_db = VuMarkDatabase(
        state=States.PROJECT_INACTIVE,
        database_name=inactive_vumark_database.target_manager_database_name,
        server_access_key=inactive_vumark_database.server_access_key,
        server_secret_key=inactive_vumark_database.server_secret_key,
    )

    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        add_flask_app_to_mock(
            mock_obj=mock,
            flask_app=VWS_FLASK_APP,
            base_url=base_vws_url,
        )

        add_flask_app_to_mock(
            mock_obj=mock,
            flask_app=CLOUDRECO_FLASK_APP,
            base_url=base_vwq_url,
        )

        add_flask_app_to_mock(
            mock_obj=mock,
            flask_app=TARGET_MANAGER_FLASK_APP,
            base_url=target_manager_base_url,
        )

        cloud_databases_url = target_manager_base_url + "/cloud_databases"
        vumark_databases_url = target_manager_base_url + "/vumark_databases"

        for database in requests.get(
            url=cloud_databases_url, timeout=30
        ).json():
            database_name: object = database["database_name"]
            assert isinstance(database_name, str)
            _ = requests.delete(
                url=cloud_databases_url + "/" + database_name,
                timeout=30,
            )
        for database in requests.get(
            url=vumark_databases_url, timeout=30
        ).json():
            database_name = database["database_name"]
            assert isinstance(database_name, str)
            _ = requests.delete(
                url=vumark_databases_url + "/" + database_name,
                timeout=30,
            )

        _ = requests.post(
            url=cloud_databases_url,
            json=working_database.to_dict(),
            timeout=30,
        )
        _ = requests.post(
            url=cloud_databases_url,
            json=inactive_cloud_database.to_dict(),
            timeout=30,
        )
        _ = requests.post(
            url=vumark_databases_url,
            json=vumark_database.to_dict(),
            timeout=30,
        )
        _ = requests.post(
            url=vumark_databases_url,
            json=inactive_vumark_db.to_dict(),
            timeout=30,
        )
        for vumark_target in vumark_database.vumark_targets:
            _ = requests.post(
                url=(
                    f"{vumark_databases_url}"
                    f"/{vumark_database.database_name}/vumark_targets"
                ),
                json=vumark_target.to_dict(),
                timeout=30,
            )

        yield


@beartype
def enable_flask_model_targets(
    *,
    monkeypatch: pytest.MonkeyPatch,
    base_vws_url: str,
) -> Generator[None]:
    """Test against the Flask-backed mock Model Target Web API."""
    assert bool(monkeypatch)
    VWS_FLASK_APP.config["VWS_MOCK_TERMINATE_WSGI_INPUT"] = True
    target_manager_base_url = "http://example.com"
    monkeypatch.setenv(
        name="TARGET_MANAGER_BASE_URL",
        value=target_manager_base_url,
    )

    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        add_flask_app_to_mock(
            mock_obj=mock,
            flask_app=VWS_FLASK_APP,
            base_url=base_vws_url,
        )

        # The VWS app stores Model Target datasets in the target manager
        # service, just as it does cloud databases.
        add_flask_app_to_mock(
            mock_obj=mock,
            flask_app=TARGET_MANAGER_FLASK_APP,
            base_url=target_manager_base_url,
        )

        yield


@beartype
def send_flask_unrouted_request(
    *,
    method: HTTPMethod,
    request_path: str,
    headers: dict[str, str],
) -> UnroutedResponse:
    """Send an unmatched request through the in-process Flask client."""
    # The ``responses`` library intercepts only the paths and methods
    # which the Flask app routes, so requests to any other path never
    # reach the app. A running container serves every path, so we drive
    # the app with its own test client.
    test_client_response = VWS_FLASK_APP.test_client().open(
        request_path,
        method=method,
        headers=headers,
    )
    response_body = test_client_response.data
    content_encoding = test_client_response.headers.get(
        key="Content-Encoding",
    )
    if content_encoding == "gzip":
        response_body = gzip.decompress(data=response_body)
    return UnroutedResponse(
        status_code=test_client_response.status_code,
        body=response_body,
        content_type=test_client_response.headers.get(
            key="Content-Type",
        ),
        content_encoding=content_encoding,
        upstream_service_time=test_client_response.headers.get(
            key="x-envoy-upstream-service-time",
        ),
    )


@beartype
def seed_flask_recognition_counts(
    *,
    database_name: str,
    target_id: str,
    current_month_recos: int,
    previous_month_recos: int,
    total_recos: int,
) -> None:
    """Set recognition counts through the target manager service."""
    target_manager_base_url = os.environ["TARGET_MANAGER_BASE_URL"]
    response = requests.post(
        url=(
            f"{target_manager_base_url}/cloud_databases/"
            f"{database_name}/targets/{target_id}/recognition_counts"
        ),
        json={
            "current_month_recos": current_month_recos,
            "previous_month_recos": previous_month_recos,
            "total_recos": total_recos,
        },
        timeout=30,
    )
    response.raise_for_status()


@beartype
def add_cloud_database(*, cloud_database: CloudDatabase) -> None:
    """Add a cloud database through the target manager service."""
    target_manager_base_url = os.environ["TARGET_MANAGER_BASE_URL"]
    response = requests.post(
        url=f"{target_manager_base_url}/cloud_databases",
        json=cloud_database.to_dict(),
        timeout=30,
    )
    response.raise_for_status()
