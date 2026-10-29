"""Choose which backends to use for the tests."""

import logging
from collections.abc import Generator
from enum import Enum
from uuid import uuid4

import pytest
from beartype import beartype
from pytest_multi_backend import backend_fixture

from vws_mock_contract_tests.fixtures.credentials import (
    InactiveVuMarkCloudDatabase,
    ModelTargetCredentials,
    VuMarkCloudDatabase,
)
from vws_mock_contract_tests.utils.backend_capabilities import (
    BackendCapabilities,
)
from vws_mock_test_backends.flask_backend import (
    enable_flask_in_process,
    enable_flask_model_targets,
)
from vws_mock_test_backends.in_memory_backend import (
    enable_in_memory_model_targets,
    enable_in_memory_vuforia,
)
from vws_mock_test_backends.real_backend import (
    enable_real_model_targets,
    enable_real_vuforia,
)
from vws_mock_test_backends.real_credentials import (
    get_model_target_credentials,
    get_real_inactive_vumark_database,
    get_real_vumark_database,
)

LOGGER = logging.getLogger(name=__name__)
LOGGER.setLevel(level=logging.DEBUG)


@pytest.fixture(name="base_vws_url")
def fixture_base_vws_url() -> str:
    """The Vuforia Web Services API URL for the backend."""
    return "https://vws.vuforia.com"


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
    VuforiaBackend.MOCK: enable_in_memory_vuforia,
    VuforiaBackend.FLASK_IN_PROCESS: enable_flask_in_process,
}

_MODEL_TARGET_SETUP_FUNCTIONS = {
    VuforiaBackend.REAL: enable_real_model_targets,
    VuforiaBackend.MOCK: enable_in_memory_model_targets,
    VuforiaBackend.FLASK_IN_PROCESS: enable_flask_model_targets,
}


# Signed Model Target requests, including state-based advanced datasets and
# standard datasets with inline CAD data, consume the Vuforia account's Model
# Target training allowance. The allowance is small, shared across all CI
# jobs, and cannot be raised or reset, so signed requests run against the real
# Vuforia only when this option is given.
VERIFY_MODEL_TARGET_SIGNING_OPTION = "--verify-model-target-signing"


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
        vumark_vuforia_database=request.getfixturevalue(
            argname="vumark_vuforia_database",
        ),
        inactive_vumark_database=request.getfixturevalue(
            argname="inactive_vumark_database",
        ),
        monkeypatch=request.getfixturevalue(argname="monkeypatch"),
        base_vws_url=request.getfixturevalue(argname="base_vws_url"),
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
    """Set up and tear down the selected VWS backend.

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
    """Set up and tear down a VWS mock backend.

    Yields:
        ``None``, once the backend is ready for mock-only tests.
    """
    yield from _setup_backend(backend=_mock_vws_backend, request=request)


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
    """The behavior supported by the running VWS backend."""
    del verify_mock_vuforia
    is_mock = _vws_backend != VuforiaBackend.REAL
    return BackendCapabilities(
        fast_oversized_content_length_response=is_mock,
    )
