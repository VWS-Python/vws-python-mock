"""Choose which backends to use for the tests."""

import contextlib
import logging
import os
from collections.abc import Generator
from enum import Enum

import pytest
import requests
import responses
from beartype import beartype
from pytest_multi_backend import backend_fixture
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
from mock_vws.request_rate_limits import DOCUMENTED_REQUEST_RATE_LIMITS
from mock_vws.states import States
from mock_vws.target import VuMarkTarget
from tests.mock_vws.fixtures.credentials import (
    InactiveVuMarkCloudDatabase,
    VuMarkCloudDatabase,
)
from tests.mock_vws.utils.cloud_databases import AddCloudDatabase
from tests.mock_vws.utils.model_target_retries import (
    retrying_transient_real_backend_failures,
)
from tests.mock_vws.utils.recognition_counts import SeedRecognitionCounts
from tests.mock_vws.utils.retries import (
    RETRY_ON_TARGET_STILL_PROCESSING,
    RETRY_ON_TRANSIENT_VWS_FAILURE,
)

LOGGER = logging.getLogger(name=__name__)
LOGGER.setLevel(level=logging.DEBUG)


@pytest.fixture(name="base_vws_url")
def fixture_base_vws_url() -> str:
    """The Vuforia Web Services API URL for the backend."""
    return "https://vws.vuforia.com"


@pytest.fixture(name="base_vwq_url")
def fixture_base_vwq_url() -> str:
    """The Vuforia Web Query API URL for the backend."""
    return "https://cloudreco.vuforia.com"


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
def _delete_all_targets(
    *, database_keys: CloudDatabase, base_vws_url: str
) -> None:
    """Delete all targets.

    Args:
        database_keys: The credentials to the Vuforia target database to delete
            all targets in.
        base_vws_url: The base URL of the services API for the backend.
    """
    vws_client = VWS(
        server_access_key=database_keys.server_access_key,
        server_secret_key=database_keys.server_secret_key,
        base_vws_url=base_vws_url,
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
        _delete_processed_target(vws_client=vws_client, target_id=target)


@beartype
@RETRY_ON_TARGET_STILL_PROCESSING
def _delete_processed_target(*, vws_client: VWS, target_id: str) -> None:
    """Delete a target which has just been waited on to be processed.

    Args:
        vws_client: A client for the database the target is in.
        target_id: The ID of the target to delete.
    """
    vws_client.delete_target(target_id=target_id)


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
    base_vws_url: str,
    base_vwq_url: str,
) -> Generator[None]:
    """Test against the real Vuforia."""
    assert bool(monkeypatch)
    assert bool(inactive_cloud_database)
    assert bool(vumark_vuforia_database)
    assert bool(inactive_vumark_database)
    del base_vwq_url
    _delete_all_targets(
        database_keys=working_database, base_vws_url=base_vws_url
    )
    yield


@beartype
def _enable_use_mock_vuforia(
    *,
    working_database: CloudDatabase,
    inactive_cloud_database: CloudDatabase,
    vumark_vuforia_database: VuMarkCloudDatabase,
    inactive_vumark_database: InactiveVuMarkCloudDatabase,
    monkeypatch: pytest.MonkeyPatch,
    base_vws_url: str,
    base_vwq_url: str,
) -> Generator[None]:
    """Test against the in-memory mock Vuforia."""
    assert bool(monkeypatch)
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

    with MockVWS(base_vws_url=base_vws_url, base_vwq_url=base_vwq_url) as mock:
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
def _enable_use_flask_in_process(
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
def _enable_use_real_model_target_vuforia(
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None]:
    """Test against the real Model Target Web API.

    Safe requests are retried past a transient gateway failure, which
    the load balancer in front of the real Model Target Web API
    occasionally returns for a request which is not at fault.
    """
    assert bool(monkeypatch)
    with retrying_transient_real_backend_failures():
        yield


@beartype
def _enable_use_mock_model_target_vuforia(
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None]:
    """Test against the in-memory mock Model Target Web API."""
    assert bool(monkeypatch)
    with MockVWS():
        yield


@beartype
def _enable_use_flask_in_process_model_target_vuforia(
    *,
    monkeypatch: pytest.MonkeyPatch,
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
    """Backends for tests.

    The names of the members give the ``--skip-backend`` options, and
    the values give the test IDs.
    """

    REAL = "Real Vuforia"
    MOCK = "In Memory Mock Vuforia"
    FLASK_IN_PROCESS = "In Process Flask Applications"


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
    VuforiaBackend.FLASK_IN_PROCESS: _enable_use_flask_in_process,
}

_MODEL_TARGET_SETUP_FUNCTIONS = {
    VuforiaBackend.REAL: _enable_use_real_model_target_vuforia,
    VuforiaBackend.MOCK: _enable_use_mock_model_target_vuforia,
    VuforiaBackend.FLASK_IN_PROCESS: (
        _enable_use_flask_in_process_model_target_vuforia
    ),
}


# Signed Model Target requests, including state-based advanced datasets and
# standard datasets with inline CAD data, consume the Vuforia account's Model
# Target training allowance. The allowance is small, shared across all CI
# jobs, and cannot be raised or reset, so signed requests run against the real
# Vuforia only when this option is given.
VERIFY_MODEL_TARGET_SIGNING_OPTION = "--verify-model-target-signing"
_INVALID_JSON_REAL_NODE_ID_PREFIXES = tuple(
    f"tests/mock_vws/invalid_json/test_invalid_json.py::{test_name}["
    "Real Vuforia-"
    for test_name in ("test_not_json", "test_not_an_object", "test_not_utf_8")
)
_INVALID_JSON_REAL_SKIP_REASON = (
    "Real Vuforia can leave malformed-body requests open indefinitely; the "
    "mock backends still verify this contract."
)
_RECO_COUNTS_REAL_NODE_ID_PART = "[Real Vuforia-reco_counts_report"
_RECO_COUNTS_REAL_SKIP_REASON = (
    "The reco counts report endpoint is unavailable to the real-Vuforia "
    "test account; the mock backends still verify this contract."
)


@beartype
def pytest_addoption(parser: pytest.Parser) -> None:
    """Add the option which opts in to signed Model Target requests.

    The options which skip backends and the Docker build tests come
    from ``pytest-multi-backend``.
    """
    parser.addoption(
        VERIFY_MODEL_TARGET_SIGNING_OPTION,
        action="store_true",
        default=False,
        help=(
            "Run signed Model Target dataset tests against the real "
            "Vuforia. These consume the account's small, shared, "
            "non-resettable Model Target training allowance, so they "
            "run against the mock backends only by default."
        ),
    )


@beartype
def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Apply infrastructure-specific test skips."""
    del config
    invalid_json_real_marker = pytest.mark.skip(
        reason=_INVALID_JSON_REAL_SKIP_REASON,
    )
    reco_counts_real_marker = pytest.mark.skip(
        reason=_RECO_COUNTS_REAL_SKIP_REASON,
    )
    for item in items:
        if item.nodeid.startswith(_INVALID_JSON_REAL_NODE_ID_PREFIXES):
            item.add_marker(marker=invalid_json_real_marker)
        if _RECO_COUNTS_REAL_NODE_ID_PART in item.nodeid:
            item.add_marker(marker=reco_counts_real_marker)


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
        base_vws_url=request.getfixturevalue(argname="base_vws_url"),
        base_vwq_url=request.getfixturevalue(argname="base_vwq_url"),
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


@beartype
def _cloud_database_adder(
    *,
    backend: VuforiaBackend,
) -> AddCloudDatabase:
    """The database creation operation for the running mock backend."""
    if backend == VuforiaBackend.MOCK:
        return running_in_memory_mock().add_cloud_database

    @beartype
    def add_flask_cloud_database(*, cloud_database: CloudDatabase) -> None:
        """Create a cloud database through the target manager service."""
        target_manager_base_url = os.environ["TARGET_MANAGER_BASE_URL"]
        response = requests.post(
            url=f"{target_manager_base_url}/cloud_databases",
            json=cloud_database.to_dict(),
            timeout=30,
        )
        response.raise_for_status()

    return add_flask_cloud_database


@pytest.fixture(name="add_cloud_database")
def fixture_add_cloud_database(
    *,
    mock_only_vuforia: VuforiaBackend,
) -> AddCloudDatabase:
    """The database creation operation for the running mock backend."""
    return _cloud_database_adder(backend=mock_only_vuforia)


@pytest.fixture(name="rate_limited_database")
def fixture_rate_limited_database(
    *,
    verify_mock_vuforia: VuforiaBackend,
    vuforia_database: CloudDatabase,
) -> CloudDatabase:
    """Return a database which applies real Vuforia's request rate limits.

    The real database applies them itself. Each mock is given a fresh
    database with the limits, so that the shared database which the other
    tests use is not limited.
    """
    if verify_mock_vuforia == VuforiaBackend.REAL:
        return vuforia_database

    database = CloudDatabase(
        request_rate_limits=DOCUMENTED_REQUEST_RATE_LIMITS
    )
    add_cloud_database = _cloud_database_adder(backend=verify_mock_vuforia)
    add_cloud_database(cloud_database=database)
    return database


@pytest.fixture(name="seed_recognition_counts")
def fixture_seed_recognition_counts(
    *,
    mock_only_vuforia: VuforiaBackend,
) -> SeedRecognitionCounts:
    """The recognition-count operation for the running mock backend."""
    if mock_only_vuforia == VuforiaBackend.MOCK:

        @beartype
        def seed_in_memory_counts(
            *,
            vuforia_database: CloudDatabase,
            target_id: str,
            current_month_recos: int,
            previous_month_recos: int,
            total_recos: int,
        ) -> None:
            """Set recognition counts through the running in-memory
            mock.
            """
            del vuforia_database
            running_in_memory_mock().set_target_recognition_counts(
                target_id=target_id,
                current_month_recos=current_month_recos,
                previous_month_recos=previous_month_recos,
                total_recos=total_recos,
            )

        return seed_in_memory_counts

    @beartype
    def seed_flask_counts(
        *,
        vuforia_database: CloudDatabase,
        target_id: str,
        current_month_recos: int,
        previous_month_recos: int,
        total_recos: int,
    ) -> None:
        """Set recognition counts through the target manager service."""
        target_manager_base_url = os.environ["TARGET_MANAGER_BASE_URL"]
        database_name = vuforia_database.database_name
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

    return seed_flask_counts
