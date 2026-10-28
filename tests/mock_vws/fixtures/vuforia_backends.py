"""Choose which backends to use for the tests."""

import contextlib
import gzip
import logging
import os
from collections.abc import Generator
from enum import Enum
from http import HTTPMethod
from typing import override
from uuid import uuid4

import pytest
import requests
import responses
from beartype import BeartypeConf, beartype
from pytest_multi_backend import backend_fixture
from requests.exceptions import Timeout as RequestsTimeout
from requests_mock_flask import add_flask_app_to_mock
from vws import VWS
from vws.exceptions.vws_exceptions import (
    TargetStatusNotSuccessError,
)
from vws.response import Response

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
    ModelTargetCredentials,
    VuMarkCloudDatabase,
)
from tests.mock_vws.fixtures.real_credentials import (
    get_model_target_credentials,
    get_real_cloud_database,
    get_real_inactive_cloud_database,
    get_real_inactive_vumark_database,
    get_real_vumark_database,
)
from tests.mock_vws.fixtures.real_model_target_retries import (
    REAL_MODEL_TARGET_RETRY_POLICY,
)
from tests.mock_vws.fixtures.real_vws_retries import REAL_VWS_RETRYING
from tests.mock_vws.utils.backend_capabilities import BackendCapabilities
from tests.mock_vws.utils.cloud_databases import AddCloudDatabase
from tests.mock_vws.utils.model_target_response_policy import (
    handling_unexpected_model_target_responses,
)
from tests.mock_vws.utils.model_target_retries import (
    retrying_model_target_requests,
)
from tests.mock_vws.utils.recognition_counts import SeedRecognitionCounts
from tests.mock_vws.utils.request_timeout_policy import (
    handling_request_timeouts,
)
from tests.mock_vws.utils.retries import (
    RETRY_ON_TARGET_STILL_PROCESSING,
    retry_transient_vws_failures,
    retrying_vws_requests,
)
from tests.mock_vws.utils.unrouted_requests import (
    UnroutedRequests,
    UnroutedResponse,
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
@retry_transient_vws_failures
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
        vws_client.wait_for_target_processed(
            target_id=target, seconds_between_requests=2
        )
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
def _handle_real_request_timeout(*, url: str, error: RequestsTimeout) -> None:
    """Skip a shared request which timed out against the real service."""
    del url, error
    pytest.skip(reason="The real Vuforia service timed out.")


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
    with (
        retrying_vws_requests(retrying=REAL_VWS_RETRYING),
        handling_request_timeouts(handler=_handle_real_request_timeout),
    ):
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

    monkeypatch.setenv(name="VWS_BASE_URL", value=base_vws_url)
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
def _handle_real_model_target_response(
    *,
    response: Response | requests.Response,
) -> None:
    """Skip an unexpected rejection by the shared real account's allowance."""
    if "TRAINING_ALLOWANCE_EXCEEDED" in response.text:
        pytest.skip(
            reason=(
                "The Vuforia account is out of Model Target training "
                "allowance - this is not a failure of the code under test."
            ),
        )


@beartype
def _enable_use_real_model_target_vuforia(
    *,
    monkeypatch: pytest.MonkeyPatch,
    base_vws_url: str,
) -> Generator[None]:
    """Test against the real Model Target Web API.

    Safe requests are retried past a transient gateway failure, which
    the load balancer in front of the real Model Target Web API
    occasionally returns for a request which is not at fault.
    """
    del base_vws_url
    assert bool(monkeypatch)
    with (
        retrying_model_target_requests(
            retrying=REAL_MODEL_TARGET_RETRY_POLICY,
        ),
        handling_request_timeouts(handler=_handle_real_request_timeout),
        handling_unexpected_model_target_responses(
            handler=_handle_real_model_target_response,
        ),
    ):
        yield


@beartype
def _enable_use_mock_model_target_vuforia(
    *,
    monkeypatch: pytest.MonkeyPatch,
    base_vws_url: str,
) -> Generator[None]:
    """Test against the in-memory mock Model Target Web API."""
    assert bool(monkeypatch)
    with MockVWS(base_vws_url=base_vws_url):
        yield


@beartype
def _enable_use_flask_in_process_model_target_vuforia(
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


@beartype
def _credential_backend(*, request: pytest.FixtureRequest) -> VuforiaBackend:
    """Read the active VWS selector without adding another backend matrix.

    Implementation tests which manage their own mock have no selector and
    receive mock credentials.
    """
    for fixture_name in ("_vws_backend", "_mock_vws_backend"):
        if fixture_name in request.fixturenames:
            backend = request.getfixturevalue(argname=fixture_name)
            assert isinstance(backend, VuforiaBackend)
            return backend
    return VuforiaBackend.MOCK


@beartype(conf=BeartypeConf(is_pep484_tower=True))
class _LiveVWS(VWS):
    """A client with a polling default suited to the live contract
    tests.
    """

    # Preserve the optional parameters of the upstream VWS API.
    @override
    def wait_for_target_processed(
        self,
        *,
        target_id: str,
        seconds_between_requests: float = 2.0,  # noqa: NOD001
        timeout_seconds: float = 60 * 5,  # noqa: NOD001
    ) -> None:
        """Poll at the cleanup interval while retaining explicit overrides."""
        super().wait_for_target_processed(
            target_id=target_id,
            seconds_between_requests=seconds_between_requests,
            timeout_seconds=timeout_seconds,
        )


@pytest.fixture(name="vws_client_class")
def fixture_vws_client_class(*, request: pytest.FixtureRequest) -> type[VWS]:
    """Use slower polling only for clients of the live Vuforia service."""
    if _credential_backend(request=request) == VuforiaBackend.REAL:
        return _LiveVWS
    return VWS


@pytest.fixture(name="vuforia_database")
def fixture_vuforia_database(
    *, request: pytest.FixtureRequest
) -> CloudDatabase:
    """An active database with credentials supplied by the backend."""
    if _credential_backend(request=request) == VuforiaBackend.REAL:
        return get_real_cloud_database()
    return CloudDatabase()


@pytest.fixture(name="inactive_cloud_database")
def fixture_inactive_cloud_database(
    *, request: pytest.FixtureRequest
) -> CloudDatabase:
    """An inactive database with credentials supplied by the backend."""
    if _credential_backend(request=request) == VuforiaBackend.REAL:
        return get_real_inactive_cloud_database()
    return CloudDatabase(state=States.PROJECT_INACTIVE)


@pytest.fixture(name="inactive_vumark_database")
def fixture_inactive_vumark_database(
    *, request: pytest.FixtureRequest
) -> InactiveVuMarkCloudDatabase:
    """An inactive VuMark database supplied by the backend."""
    if _credential_backend(request=request) == VuforiaBackend.REAL:
        return get_real_inactive_vumark_database()
    return InactiveVuMarkCloudDatabase(
        target_manager_database_name=uuid4().hex,
        server_access_key=uuid4().hex,
        server_secret_key=uuid4().hex,
    )


@pytest.fixture(name="vumark_vuforia_database")
def fixture_vumark_vuforia_database(
    *, request: pytest.FixtureRequest
) -> VuMarkCloudDatabase:
    """A VuMark database with credentials supplied by the backend."""
    if _credential_backend(request=request) == VuforiaBackend.REAL:
        return get_real_vumark_database()
    return VuMarkCloudDatabase(
        target_manager_database_name=uuid4().hex,
        server_access_key=uuid4().hex,
        server_secret_key=uuid4().hex,
        target_id=uuid4().hex,
        processing_target_id=uuid4().hex,
    )


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
        base_vws_url=request.getfixturevalue(argname="base_vws_url"),
    )


@beartype
def _defer_backend_setup(
    *,
    backend: VuforiaBackend,
    request: pytest.FixtureRequest,
) -> Generator[None]:
    """Leave setup to the shared fixture after backend selection.

    Yields:
        ``None``, without setting up the selected backend.
    """
    del backend, request
    yield


# These adapter-internal fixtures select and apply skip policy for a backend.
# Public fixtures below set up and tear down the selected backend without
# exposing that selection to the shared suite.
fixture_vws_backend = backend_fixture(
    name="_vws_backend",
    backends=_ALL_BACKENDS,
    setup_for=_defer_backend_setup,
)
fixture_model_target_backend = backend_fixture(
    name="_model_target_backend",
    backends=_ALL_BACKENDS,
    setup_for=_defer_backend_setup,
)
fixture_model_target_mock_backend = backend_fixture(
    name="_model_target_mock_backend",
    backends=_MOCK_BACKENDS,
    setup_for=_defer_backend_setup,
)
fixture_mock_vws_backend = backend_fixture(
    name="_mock_vws_backend",
    backends=_MOCK_BACKENDS,
    setup_for=_defer_backend_setup,
)


@pytest.fixture(name="verify_mock_vuforia")
def fixture_verify_mock_vuforia(
    *,
    _vws_backend: VuforiaBackend,
    request: pytest.FixtureRequest,
) -> Generator[None]:
    """Set up and tear down the selected VWS/query backend.

    Yields:
        ``None``, once the backend is ready for shared tests.
    """
    yield from _setup_backend(backend=_vws_backend, request=request)


@pytest.fixture(name="verify_model_target_mock_vuforia")
def fixture_verify_model_target_mock_vuforia(
    *,
    _model_target_backend: VuforiaBackend,
    request: pytest.FixtureRequest,
) -> Generator[None]:
    """Set up and tear down the selected Model Target backend.

    Yields:
        ``None``, once the backend is ready for shared tests.
    """
    yield from _setup_model_target_backend(
        backend=_model_target_backend,
        request=request,
    )


@pytest.fixture(name="model_target_mock_only_vuforia")
def fixture_model_target_mock_only_vuforia(
    *,
    _model_target_mock_backend: VuforiaBackend,
    request: pytest.FixtureRequest,
) -> Generator[None]:
    """Set up and tear down a Model Target mock backend.

    Yields:
        ``None``, once the backend is ready for mock-only tests.
    """
    yield from _setup_model_target_backend(
        backend=_model_target_mock_backend,
        request=request,
    )


@pytest.fixture(name="mock_only_vuforia")
def fixture_mock_only_vuforia(
    *,
    _mock_vws_backend: VuforiaBackend,
    request: pytest.FixtureRequest,
) -> Generator[None]:
    """Set up and tear down a VWS/query mock backend.

    Yields:
        ``None``, once the backend is ready for mock-only tests.
    """
    yield from _setup_backend(backend=_mock_vws_backend, request=request)


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
    mock_only_vuforia: None,
    _mock_vws_backend: VuforiaBackend,
) -> AddCloudDatabase:
    """The database creation operation for the running mock backend."""
    del mock_only_vuforia
    return _cloud_database_adder(backend=_mock_vws_backend)


@pytest.fixture(name="rate_limited_database")
def fixture_rate_limited_database(
    *,
    verify_mock_vuforia: None,
    _vws_backend: VuforiaBackend,
    vuforia_database: CloudDatabase,
) -> CloudDatabase:
    """Return a database which applies real Vuforia's request rate limits.

    The real database applies them itself. Each mock is given a fresh
    database with the limits, so that the shared database which the other
    tests use is not limited.
    """
    del verify_mock_vuforia
    if _vws_backend == VuforiaBackend.REAL:
        return vuforia_database

    database = CloudDatabase(
        request_rate_limits=DOCUMENTED_REQUEST_RATE_LIMITS
    )
    add_cloud_database = _cloud_database_adder(backend=_vws_backend)
    add_cloud_database(cloud_database=database)
    return database


@pytest.fixture(name="seed_recognition_counts")
def fixture_seed_recognition_counts(
    *,
    mock_only_vuforia: None,
    _mock_vws_backend: VuforiaBackend,
) -> SeedRecognitionCounts:
    """The recognition-count operation for the running mock backend."""
    del mock_only_vuforia
    if _mock_vws_backend == VuforiaBackend.MOCK:

        @beartype
        def seed_in_memory_counts(
            *,
            database_name: str,
            target_id: str,
            current_month_recos: int,
            previous_month_recos: int,
            total_recos: int,
        ) -> None:
            """Set recognition counts through the running in-memory
            mock.
            """
            del database_name
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

    return seed_flask_counts


@pytest.fixture(name="unrouted_requests")
def fixture_unrouted_requests(
    *,
    verify_mock_vuforia: None,
    _vws_backend: VuforiaBackend,
    base_vws_url: str,
) -> UnroutedRequests:
    """The transport for unmatched requests on the running backend."""
    del verify_mock_vuforia
    if _vws_backend == VuforiaBackend.FLASK_IN_PROCESS:
        return UnroutedRequests(
            send=_send_flask_unrouted_request,
            returns_response=True,
        )

    @beartype
    def send_http_request(
        *,
        method: HTTPMethod,
        request_path: str,
        headers: dict[str, str],
    ) -> UnroutedResponse | None:
        """Send an unmatched request to the configured VWS URL."""
        try:
            response = requests.request(
                method=method,
                url=base_vws_url + request_path,
                headers=headers,
                timeout=30,
            )
        except requests.exceptions.ConnectionError:
            return None

        return UnroutedResponse(
            status_code=response.status_code,
            body=response.content,
            content_type=response.headers.get("Content-Type"),
            content_encoding=response.headers.get("Content-Encoding"),
            upstream_service_time=response.headers.get(
                "x-envoy-upstream-service-time",
            ),
        )

    return UnroutedRequests(
        send=send_http_request,
        returns_response=_vws_backend != VuforiaBackend.MOCK,
    )


@beartype
def _send_flask_unrouted_request(
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
def _model_target_credentials_for_backend(
    *,
    backend: VuforiaBackend,
) -> ModelTargetCredentials:
    """Return Model Target credentials for the chosen backend."""
    if backend == VuforiaBackend.REAL:
        return get_model_target_credentials()

    return ModelTargetCredentials(
        client_id="client-id",
        client_secret="client-secret",
        cad_data_url="https://example.com/model.glb",
        username="user@example.com",
        password="password",
    )


@pytest.fixture(name="model_target_credentials")
def fixture_model_target_credentials(
    *,
    verify_model_target_mock_vuforia: None,
    _model_target_backend: VuforiaBackend,
) -> ModelTargetCredentials:
    """Model Target credentials supplied by the running backend."""
    del verify_model_target_mock_vuforia
    return _model_target_credentials_for_backend(
        backend=_model_target_backend,
    )


@pytest.fixture(name="mock_model_target_credentials")
def fixture_mock_model_target_credentials(
    *,
    model_target_mock_only_vuforia: None,
    _model_target_mock_backend: VuforiaBackend,
) -> ModelTargetCredentials:
    """Model Target credentials for tests which require a mock."""
    del model_target_mock_only_vuforia
    return _model_target_credentials_for_backend(
        backend=_model_target_mock_backend,
    )


# Creating an advanced dataset with a state-based configuration or a standard
# dataset with inline CAD data is a "signed" request: the real Vuforia signs
# the trained dataset, and each signing consumes the account's allowance. The
# allowance is tiny (roughly 20 signings, under ten CI runs' worth), it
# is shared by every CI job and every concurrent run, and it cannot be
# raised or reset by us.  Verifying this behavior on every run therefore
# burns the whole allowance within hours and then turns every CI run red
# with ``TRAINING_ALLOWANCE_EXCEEDED`` - which is exactly what happened
# when it ran unconditionally.  The equivalent unsigned requests (a
# standard dataset, or an advanced dataset without a state-based
# configuration) are far cheaper and stay enabled, though with enough
# traffic they can also hit the allowance; an unexpected allowance
# rejection is skipped by the real adapter rather than failing the run.
_SIGNED_REQUEST_SKIP_REASON = (
    "Signed Model Target requests consume the real Vuforia account's "
    "small, shared, non-resettable training allowance, so they are not "
    "verified against the real Vuforia by default. Pass "
    f"{VERIFY_MODEL_TARGET_SIGNING_OPTION} to verify them, for example "
    "after the allowance has recovered. The mock backends always run "
    "this test."
)


def _skip_unrequested_real_signing(
    *,
    request: pytest.FixtureRequest,
    backend: VuforiaBackend,
) -> None:
    """Skip a signing request against real Vuforia unless opted in."""
    if backend is VuforiaBackend.REAL and not request.config.getoption(
        name=VERIFY_MODEL_TARGET_SIGNING_OPTION,
    ):
        pytest.skip(reason=_SIGNED_REQUEST_SKIP_REASON)


@pytest.fixture(name="signed_model_target_credentials")
def fixture_signed_model_target_credentials(
    *,
    verify_model_target_mock_vuforia: None,
    _model_target_backend: VuforiaBackend,
    request: pytest.FixtureRequest,
) -> ModelTargetCredentials:
    """Credentials for signing tests, after applying the real-service
    opt-in policy.
    """
    del verify_model_target_mock_vuforia
    _skip_unrequested_real_signing(
        request=request,
        backend=_model_target_backend,
    )
    return _model_target_credentials_for_backend(
        backend=_model_target_backend,
    )


@pytest.fixture(name="backend_capabilities")
def fixture_backend_capabilities(
    *,
    verify_mock_vuforia: None,
    _vws_backend: VuforiaBackend,
) -> BackendCapabilities:
    """The behavior supported by the running VWS and query backend."""
    del verify_mock_vuforia
    is_mock = _vws_backend != VuforiaBackend.REAL
    return BackendCapabilities(
        deterministic_target_order=is_mock,
        deterministic_query_order=is_mock,
        fast_oversized_content_length_response=is_mock,
        rolling_rate_limit_window=is_mock,
    )
