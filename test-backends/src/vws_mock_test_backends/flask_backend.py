"""Flask transport setup and controls for the contract-test adapter."""

from collections.abc import Generator

import pytest
import requests
import responses
from beartype import beartype
from requests_mock_flask import add_flask_app_to_mock

from mock_vws.database import VuMarkDatabase
from mock_vws.states import States
from vws_mock_contract_tests.fixtures.credentials import (
    InactiveVuMarkCloudDatabase,
    VuMarkCloudDatabase,
)
from vws_mock_server.target_manager import TARGET_MANAGER_FLASK_APP
from vws_mock_server.vws import VWS_FLASK_APP
from vws_mock_test_backends.mock_databases import create_vumark_database


@beartype
def enable_flask_in_process(
    *,
    vumark_vuforia_database: VuMarkCloudDatabase,
    inactive_vumark_database: InactiveVuMarkCloudDatabase,
    monkeypatch: pytest.MonkeyPatch,
    base_vws_url: str,
) -> Generator[None]:
    """Test against the Flask applications of the mock, in this process.

    This exercises the handlers of the Flask applications which the
    Docker deployment runs, but not the deployment itself: all three
    applications are served from one process, so state which the
    deployment keeps in separate containers is shared here.
    The Docker deployment tests cover the container split.
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
            flask_app=TARGET_MANAGER_FLASK_APP,
            base_url=target_manager_base_url,
        )

        vumark_databases_url = target_manager_base_url + "/vumark_databases"

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
        # service alongside VuMark databases.
        add_flask_app_to_mock(
            mock_obj=mock,
            flask_app=TARGET_MANAGER_FLASK_APP,
            base_url=target_manager_base_url,
        )

        yield
