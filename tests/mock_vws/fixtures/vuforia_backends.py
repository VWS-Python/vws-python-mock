"""Choose which backends to use for the tests."""

import contextlib
import logging
from collections.abc import Generator
from enum import Enum

import pytest
import requests
import responses
from beartype import beartype
from requests_mock_flask import add_flask_app_to_mock
from vws import VWS
from vws.exceptions.vws_exceptions import (
    TargetStatusNotSuccessError,
)

from mock_vws import MockVWS
from mock_vws._flask_server.target_manager import TARGET_MANAGER_FLASK_APP
from mock_vws._flask_server.vwq import CLOUDRECO_FLASK_APP
from mock_vws._flask_server.vws import VWS_FLASK_APP
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.states import States
from mock_vws.target import VuMarkTarget
from tests.backend_harness import add_skip_options, backend_fixture
from tests.mock_vws.fixtures.credentials import (
    InactiveVuMarkCloudDatabase,
    VuMarkCloudDatabase,
)
from tests.mock_vws.utils.retries import RETRY_ON_TRANSIENT_VWS_FAILURE

LOGGER = logging.getLogger(name=__name__)
LOGGER.setLevel(level=logging.DEBUG)

# The in-memory mock which the ``MOCK`` backend is running, if any.
#
# Tests which use APIs of the mock itself, such as seeding recognition counts,
# need the mock which the fixture created. This is a list so that the fixture
# can set and unset it without a ``global`` statement.
_RUNNING_IN_MEMORY_MOCKS: list[MockVWS] = []


@beartype
def running_in_memory_mock() -> MockVWS:
    """The in-memory mock which the ``MOCK`` backend is running.

    Returns:
        The mock which the ``MOCK`` backend set up for the running test.
        Indexing fails if the ``MOCK`` backend is not running.
    """
    return _RUNNING_IN_MEMORY_MOCKS[0]


@beartype
@RETRY_ON_TRANSIENT_VWS_FAILURE
def _delete_all_targets(*, database_keys: CloudDatabase) -> None:
    """Delete all targets.

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
        with contextlib.suppress(TargetStatusNotSuccessError):
            vws_client.update_target(target_id=target, active_flag=False)
        vws_client.wait_for_target_processed(target_id=target)
        vws_client.delete_target(target_id=target)


@beartype
def _vumark_database(
    *,
    vumark_vuforia_database: VuMarkCloudDatabase,
) -> VuMarkDatabase:
    """Return a database with a VuMark target for VuMark instance
    generation.
    """
    vumark_target = VuMarkTarget(
        name="mock-vumark-target",
        target_id=vumark_vuforia_database.target_id,
    )
    processing_target = VuMarkTarget(
        name="mock-processing-vumark-target",
        target_id=vumark_vuforia_database.processing_target_id,
        processing_time_seconds=9999,
    )
    return VuMarkDatabase(
        database_name=vumark_vuforia_database.target_manager_database_name,
        server_access_key=vumark_vuforia_database.server_access_key,
        server_secret_key=vumark_vuforia_database.server_secret_key,
        vumark_targets={vumark_target, processing_target},
    )


@beartype
def _enable_use_real_vuforia(
    *,
    working_database: CloudDatabase,
    inactive_cloud_database: CloudDatabase,
    vumark_vuforia_database: VuMarkCloudDatabase,
    inactive_vumark_database: InactiveVuMarkCloudDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None]:
    """Test against the real Vuforia."""
    assert monkeypatch
    assert inactive_cloud_database
    assert vumark_vuforia_database
    assert inactive_vumark_database
    _delete_all_targets(database_keys=working_database)
    yield


@beartype
def _enable_use_mock_vuforia(
    *,
    working_database: CloudDatabase,
    inactive_cloud_database: CloudDatabase,
    vumark_vuforia_database: VuMarkCloudDatabase,
    inactive_vumark_database: InactiveVuMarkCloudDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None]:
    """Test against the in-memory mock Vuforia."""
    assert monkeypatch
    working_database = CloudDatabase(
        database_id=working_database.database_id,
        database_name=working_database.database_name,
        server_access_key=working_database.server_access_key,
        server_secret_key=working_database.server_secret_key,
        client_access_key=working_database.client_access_key,
        client_secret_key=working_database.client_secret_key,
    )

    inactive_cloud_database = CloudDatabase(
        state=States.PROJECT_INACTIVE,
        database_name=inactive_cloud_database.database_name,
        server_access_key=inactive_cloud_database.server_access_key,
        server_secret_key=inactive_cloud_database.server_secret_key,
        client_access_key=inactive_cloud_database.client_access_key,
        client_secret_key=inactive_cloud_database.client_secret_key,
    )
    vumark_database = _vumark_database(
        vumark_vuforia_database=vumark_vuforia_database,
    )
    inactive_vumark_db = VuMarkDatabase(
        state=States.PROJECT_INACTIVE,
        database_name=inactive_vumark_database.target_manager_database_name,
        server_access_key=inactive_vumark_database.server_access_key,
        server_secret_key=inactive_vumark_database.server_secret_key,
    )

    with MockVWS() as mock:
        mock.add_cloud_database(cloud_database=working_database)
        mock.add_cloud_database(cloud_database=inactive_cloud_database)
        mock.add_vumark_database(vumark_database=vumark_database)
        mock.add_vumark_database(vumark_database=inactive_vumark_db)
        _RUNNING_IN_MEMORY_MOCKS.append(mock)
        try:
            yield
        finally:
            _RUNNING_IN_MEMORY_MOCKS.remove(mock)


@beartype
def _enable_use_docker_in_memory(
    *,
    working_database: CloudDatabase,
    inactive_cloud_database: CloudDatabase,
    vumark_vuforia_database: VuMarkCloudDatabase,
    inactive_vumark_database: InactiveVuMarkCloudDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None]:
    """Test against mock Vuforia created to be run in a container."""
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
    vumark_database = _vumark_database(
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

        cloud_databases_url = target_manager_base_url + "/cloud_databases"
        vumark_databases_url = target_manager_base_url + "/vumark_databases"

        for database in requests.get(
            url=cloud_databases_url, timeout=30
        ).json():
            requests.delete(
                url=cloud_databases_url + "/" + database["database_name"],
                timeout=30,
            )
        for database in requests.get(
            url=vumark_databases_url, timeout=30
        ).json():
            requests.delete(
                url=vumark_databases_url + "/" + database["database_name"],
                timeout=30,
            )

        requests.post(
            url=cloud_databases_url,
            json=working_database.to_dict(),
            timeout=30,
        )
        requests.post(
            url=cloud_databases_url,
            json=inactive_cloud_database.to_dict(),
            timeout=30,
        )
        requests.post(
            url=vumark_databases_url,
            json=vumark_database.to_dict(),
            timeout=30,
        )
        requests.post(
            url=vumark_databases_url,
            json=inactive_vumark_db.to_dict(),
            timeout=30,
        )
        for vumark_target in vumark_database.vumark_targets:
            requests.post(
                url=(
                    f"{vumark_databases_url}"
                    f"/{vumark_database.database_name}/vumark_targets"
                ),
                json=vumark_target.to_dict(),
                timeout=30,
            )

        yield


@beartype
def _enable_use_real_model_target_vuforia(
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None]:
    """Test against the real Model Target Web API."""
    assert monkeypatch
    yield


@beartype
def _enable_use_mock_model_target_vuforia(
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None]:
    """Test against the in-memory mock Model Target Web API."""
    assert monkeypatch
    with MockVWS():
        yield


@beartype
def _enable_use_docker_in_memory_model_target_vuforia(
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None]:
    """Test against the Flask-backed mock Model Target Web API."""
    assert monkeypatch
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
            base_url="https://vws.vuforia.com",
        )

        # The VWS app stores Model Target datasets in the target manager
        # service, just as it does cloud databases.
        add_flask_app_to_mock(
            mock_obj=mock,
            flask_app=TARGET_MANAGER_FLASK_APP,
            base_url=target_manager_base_url,
        )

        yield


class VuforiaBackend(Enum):
    """Backends for tests."""

    REAL = "Real Vuforia"
    MOCK = "In Memory Mock Vuforia"
    DOCKER_IN_MEMORY = "In Memory version of Docker application"


_ALL_BACKENDS = list(VuforiaBackend)
# The real Vuforia cannot be set up for tests which need to control the
# state of the service.
_MOCK_BACKENDS = [
    backend for backend in _ALL_BACKENDS if backend != VuforiaBackend.REAL
]

# These deliberately have no type annotation, so that the keyword
# arguments of the setup functions are still checked where they are
# bound.
_SETUP_FUNCTIONS = {
    VuforiaBackend.REAL: _enable_use_real_vuforia,
    VuforiaBackend.MOCK: _enable_use_mock_vuforia,
    VuforiaBackend.DOCKER_IN_MEMORY: _enable_use_docker_in_memory,
}

_MODEL_TARGET_SETUP_FUNCTIONS = {
    VuforiaBackend.REAL: _enable_use_real_model_target_vuforia,
    VuforiaBackend.MOCK: _enable_use_mock_model_target_vuforia,
    VuforiaBackend.DOCKER_IN_MEMORY: (
        _enable_use_docker_in_memory_model_target_vuforia
    ),
}


@beartype
def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Add options to the pytest command line for skipping tests with
    particular
    backends.
    """
    add_skip_options(parser=parser, backends=_ALL_BACKENDS)

    parser.addoption(
        "--skip-docker_build_tests",
        action="store_true",
        default=False,
        help="Skip tests for building Docker images",
    )


@beartype
def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip Docker tests if requested."""
    skip_docker_build_tests_option = "--skip-docker_build_tests"
    skip_docker_build_tests_marker = pytest.mark.skip(
        reason=(
            "Skipping docker build tests because "
            f"{skip_docker_build_tests_option} was set"
        ),
    )
    if config.getoption(name=skip_docker_build_tests_option):
        for item in items:
            if "requires_docker_build" in item.keywords:
                item.add_marker(marker=skip_docker_build_tests_marker)


@beartype
def _setup_backend(
    *,
    backend: VuforiaBackend,
    request: pytest.FixtureRequest,
) -> Generator[None]:
    """Set a backend up with the databases which the tests use.

    Yields:
        ``None``, once the backend is set up.
    """
    yield from _SETUP_FUNCTIONS[backend](
        working_database=request.getfixturevalue(argname="vuforia_database"),
        inactive_cloud_database=request.getfixturevalue(
            argname="inactive_cloud_database",
        ),
        vumark_vuforia_database=request.getfixturevalue(
            argname="vumark_vuforia_database",
        ),
        inactive_vumark_database=request.getfixturevalue(
            argname="inactive_vumark_database",
        ),
        monkeypatch=request.getfixturevalue(argname="monkeypatch"),
    )


@beartype
def _setup_model_target_backend(
    *,
    backend: VuforiaBackend,
    request: pytest.FixtureRequest,
) -> Generator[None]:
    """Set a backend up for the Model Target Web API tests.

    Yields:
        ``None``, once the backend is set up.
    """
    yield from _MODEL_TARGET_SETUP_FUNCTIONS[backend](
        monkeypatch=request.getfixturevalue(argname="monkeypatch"),
    )


# Tests which use this are run against the real Vuforia and against each
# mock. This is useful for verifying the mocks.
fixture_verify_mock_vuforia = backend_fixture(
    name="verify_mock_vuforia",
    backends=_ALL_BACKENDS,
    setup_for=_setup_backend,
)

# Model Target Web API contract tests, run against the real Vuforia and
# against each mock.
fixture_verify_model_target_mock_vuforia = backend_fixture(
    name="verify_model_target_mock_vuforia",
    backends=_ALL_BACKENDS,
    setup_for=_setup_model_target_backend,
)

# Model Target Web API tests which need scopes that the real test account does
# not have, run against each mock only.
fixture_model_target_mock_only_vuforia = backend_fixture(
    name="model_target_mock_only_vuforia",
    backends=_MOCK_BACKENDS,
    setup_for=_setup_model_target_backend,
)

# Tests which use this are run against each mock, and not against the
# real Vuforia. This is useful for testing the mock using fixtures which
# connect to Vuforia.
fixture_mock_only_vuforia = backend_fixture(
    name="mock_only_vuforia",
    backends=_MOCK_BACKENDS,
    setup_for=_setup_backend,
)
