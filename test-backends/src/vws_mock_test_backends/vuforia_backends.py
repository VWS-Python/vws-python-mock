"""Choose which backends to use for the tests."""

import logging
from collections.abc import Generator
from enum import Enum
from http import HTTPMethod
from uuid import uuid4

import pytest
import requests
from beartype import beartype
from pytest_multi_backend import backend_fixture
from vws import VWS

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.request_rate_limits import DOCUMENTED_REQUEST_RATE_LIMITS
from mock_vws.states import States
from vws_mock_contract_tests.fixtures.credentials import (
    InactiveVuMarkCloudDatabase,
    ModelTargetCredentials,
    NamedCloudDatabaseCredentials,
    VuMarkCloudDatabase,
)
from vws_mock_contract_tests.utils.backend_capabilities import (
    BackendCapabilities,
)
from vws_mock_contract_tests.utils.cloud_databases import CreateCloudDatabase
from vws_mock_contract_tests.utils.recognition_counts import (
    SeedRecognitionCounts,
)
from vws_mock_contract_tests.utils.unrouted_requests import (
    UnroutedRequests,
    UnroutedResponse,
)
from vws_mock_test_backends.flask_backend import (
    add_cloud_database,
    enable_flask_in_process,
    enable_flask_model_targets,
    seed_flask_recognition_counts,
    send_flask_unrouted_request,
)
from vws_mock_test_backends.mock_databases import create_vumark_database
from vws_mock_test_backends.real_backend import (
    LiveVWS,
    enable_real_model_targets,
    enable_real_vuforia,
)
from vws_mock_test_backends.real_credentials import (
    get_model_target_credentials,
    get_real_cloud_database,
    get_real_inactive_cloud_database,
    get_real_inactive_vumark_database,
    get_real_vumark_database,
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
    vumark_database = create_vumark_database(
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
def _enable_use_mock_model_target_vuforia(
    *,
    monkeypatch: pytest.MonkeyPatch,
    base_vws_url: str,
) -> Generator[None]:
    """Test against the in-memory mock Model Target Web API."""
    assert bool(monkeypatch)
    with MockVWS(base_vws_url=base_vws_url):
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


@pytest.fixture(name="vws_client_class")
def fixture_vws_client_class(*, request: pytest.FixtureRequest) -> type[VWS]:
    """Use slower polling only for clients of the live Vuforia service."""
    if _credential_backend(request=request) == VuforiaBackend.REAL:
        return LiveVWS
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
    VuforiaBackend.REAL: enable_real_vuforia,
    VuforiaBackend.MOCK: _enable_use_mock_vuforia,
    VuforiaBackend.FLASK_IN_PROCESS: enable_flask_in_process,
}

_MODEL_TARGET_SETUP_FUNCTIONS = {
    VuforiaBackend.REAL: enable_real_model_targets,
    VuforiaBackend.MOCK: _enable_use_mock_model_target_vuforia,
    VuforiaBackend.FLASK_IN_PROCESS: enable_flask_model_targets,
}


# Signed Model Target requests, including state-based advanced datasets and
# standard datasets with inline CAD data, consume the Vuforia account's Model
# Target training allowance. The allowance is small, shared across all CI
# jobs, and cannot be raised or reset, so signed requests run against the real
# Vuforia only when this option is given.
VERIFY_MODEL_TARGET_SIGNING_OPTION = "--verify-model-target-signing"
_INVALID_JSON_REAL_ITEM_PREFIXES = tuple(
    f"{test_name}[Real Vuforia-"
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
        if item.path.parts[-2:] == (
            "invalid_json",
            "test_invalid_json.py",
        ) and item.name.startswith(_INVALID_JSON_REAL_ITEM_PREFIXES):
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
def _add_cloud_database(
    *,
    backend: VuforiaBackend,
    cloud_database: CloudDatabase,
) -> None:
    """Add a database through the running mock backend."""
    if backend == VuforiaBackend.MOCK:
        running_in_memory_mock().add_cloud_database(
            cloud_database=cloud_database,
        )
        return

    add_cloud_database(cloud_database=cloud_database)


@pytest.fixture(name="create_cloud_database")
def fixture_create_cloud_database(
    *,
    mock_only_vuforia: None,
    _mock_vws_backend: VuforiaBackend,
) -> CreateCloudDatabase:
    """The database creation operation for the running mock backend."""
    del mock_only_vuforia

    @beartype
    def create_database() -> NamedCloudDatabaseCredentials:
        """Create a fresh database through the selected backend."""
        database = CloudDatabase()
        _add_cloud_database(
            backend=_mock_vws_backend,
            cloud_database=database,
        )
        return database

    return create_database


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
    _add_cloud_database(backend=_vws_backend, cloud_database=database)
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

    return seed_flask_recognition_counts


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
            send=send_flask_unrouted_request,
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
