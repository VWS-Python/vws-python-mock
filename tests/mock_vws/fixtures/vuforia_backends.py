"""
Choose which backends to use for the tests.
"""
from __future__ import annotations

import contextlib
import logging
from enum import Enum
from typing import TYPE_CHECKING

import pytest
import requests
import requests_mock
from mock_vws import MockVWS
from mock_vws._flask_server.target_manager import TARGET_MANAGER_FLASK_APP
from mock_vws._flask_server.vwq import CLOUDRECO_FLASK_APP
from mock_vws._flask_server.vws import VWS_FLASK_APP
from mock_vws.database import VuforiaDatabase
from mock_vws.states import States
from requests_mock_flask import add_flask_app_to_mock
from vws import VWS
from vws.exceptions.vws_exceptions import (
    TargetStatusNotSuccess,
)

from tests.mock_vws.utils.retries import RETRY_ON_TOO_MANY_REQUESTS

if TYPE_CHECKING:
    from collections.abc import Generator


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


@RETRY_ON_TOO_MANY_REQUESTS
def _delete_all_targets(database_keys: VuforiaDatabase) -> None:
    """
    Delete all targets.

    Args:
        database_keys: The credentials to the Vuforia target database to delete
            all targets in.
    """
    vws_client = VWS(
        server_access_key=database_keys.server_access_key,
        server_secret_key=database_keys.server_secret_key,
    )

    targets = vws_client.list_targets()

    for target in targets:
        vws_client.wait_for_target_processed(
            target_id=target,
            # Setting this to 2 is an attempt to avoid 429 Too Many Requests
            # errors.
            seconds_between_requests=2,
        )
        # Even deleted targets can be matched by a query for a few seconds so
        # we change the target to inactive before deleting it.
        with contextlib.suppress(TargetStatusNotSuccess):
            vws_client.update_target(target_id=target, active_flag=False)
        vws_client.wait_for_target_processed(target_id=target)
        vws_client.delete_target(target_id=target)


def _enable_use_real_vuforia(
    working_database: VuforiaDatabase,
    inactive_database: VuforiaDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    assert monkeypatch
    assert inactive_database
    _delete_all_targets(database_keys=working_database)
    yield


def _enable_use_mock_vuforia(
    working_database: VuforiaDatabase,
    inactive_database: VuforiaDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    assert monkeypatch
    working_database = VuforiaDatabase(
        database_name=working_database.database_name,
        server_access_key=working_database.server_access_key,
        server_secret_key=working_database.server_secret_key,
        client_access_key=working_database.client_access_key,
        client_secret_key=working_database.client_secret_key,
    )

    inactive_database = VuforiaDatabase(
        state=States.PROJECT_INACTIVE,
        database_name=inactive_database.database_name,
        server_access_key=inactive_database.server_access_key,
        server_secret_key=inactive_database.server_secret_key,
        client_access_key=inactive_database.client_access_key,
        client_secret_key=inactive_database.client_secret_key,
    )

    with MockVWS() as mock:
        mock.add_database(database=working_database)
        mock.add_database(database=inactive_database)
        yield


def _enable_use_docker_in_memory(
    working_database: VuforiaDatabase,
    inactive_database: VuforiaDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
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

    target_manager_base_url = "http://example.com"
    monkeypatch.setenv(
        name="TARGET_MANAGER_BASE_URL",
        value=target_manager_base_url,
    )

    with requests_mock.Mocker(real_http=False) as mock:
        add_flask_app_to_mock(
            mock_obj=mock,
            flask_app=VWS_FLASK_APP,
            base_url="https://vws.vuforia.com",
        )

        add_flask_app_to_mock(
            mock_obj=mock,
            flask_app=CLOUDRECO_FLASK_APP,
            base_url="https://cloudreco.vuforia.com",
        )

        add_flask_app_to_mock(
            mock_obj=mock,
            flask_app=TARGET_MANAGER_FLASK_APP,
            base_url=target_manager_base_url,
        )

        databases_url = target_manager_base_url + "/databases"
        databases = requests.get(
            url=databases_url,
            timeout=30,
        ).json()
        for database in databases:
            database_name = database["database_name"]
            requests.delete(
                url=databases_url + "/" + database_name,
                timeout=30,
            )

        requests.post(
            url=databases_url,
            json=working_database.to_dict(),
            timeout=30,
        )
        requests.post(
            url=databases_url,
            json=inactive_database.to_dict(),
            timeout=30,
        )

        yield


class VuforiaBackend(Enum):
    """
    Backends for tests.
    """

    REAL = "Real Vuforia"
    MOCK = "In Memory Mock Vuforia"
    DOCKER_IN_MEMORY = "In Memory version of Docker application"


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Add options to the pytest command line for skipping tests with particular
    backends.
    """
    for backend in VuforiaBackend:
        parser.addoption(
            f"--skip-{backend.name.lower()}",
            action="store_true",
            default=False,
            help=f"Skip tests for {backend.value}",
        )

    parser.addoption(
        "--skip-docker_build_tests",
        action="store_true",
        default=False,
        help="Skip tests for building Docker images",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Function],
) -> None:
    """Skip Docker tests if requested."""
    skip_docker_build_tests_option = "--skip-docker_build_tests"
    skip_docker_build_tests_marker = pytest.mark.skip(
        reason=(
            "Skipping docker build tests because "
            f"{skip_docker_build_tests_option} was set"
        ),
    )
    if config.getoption(skip_docker_build_tests_option):
        for item in items:
            if "requires_docker_build" in item.keywords:
                item.add_marker(skip_docker_build_tests_marker)


@pytest.fixture(
    params=list(VuforiaBackend),
    ids=[backend.value for backend in list(VuforiaBackend)],
)
def verify_mock_vuforia(
    request: pytest.FixtureRequest,
    vuforia_database: VuforiaDatabase,
    inactive_database: VuforiaDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """
    Test functions which use this fixture are run multiple times. Once with the
    real Vuforia, and once with each mock.

    This is useful for verifying the mocks.

    Yields:
        ``None``.
    """
    backend = request.param
    should_skip = request.config.getoption(f"--skip-{backend.name.lower()}")
    if should_skip:
        pytest.skip()

    enable_function = {
        VuforiaBackend.REAL: _enable_use_real_vuforia,
        VuforiaBackend.MOCK: _enable_use_mock_vuforia,
        VuforiaBackend.DOCKER_IN_MEMORY: _enable_use_docker_in_memory,
    }[backend]

    yield from enable_function(
        working_database=vuforia_database,
        inactive_database=inactive_database,
        monkeypatch=monkeypatch,
    )
