"""Tests for timeout handling supplied by backend adapters."""

from collections.abc import Generator
from http import HTTPMethod, HTTPStatus

import pytest
import requests
from requests.exceptions import ConnectTimeout, ReadTimeout
from requests.exceptions import Timeout as RequestsTimeout
from vws import VWS

from mock_vws.database import CloudDatabase
from mock_vws.states import States
from tests.mock_vws.fixtures import vuforia_backends
from tests.mock_vws.fixtures.credentials import (
    InactiveVuMarkCloudDatabase,
    VuMarkCloudDatabase,
)
from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend
from tests.mock_vws.utils import Endpoint, ModelTargetEndpoint
from tests.mock_vws.utils.request_timeout_policy import (
    handle_request_timeout,
    handling_request_timeouts,
)


@pytest.fixture(name="_vws_backend")
def fixture_vws_backend() -> VuforiaBackend:
    """Select the real policy using synthetic credentials and
    transport.
    """
    return VuforiaBackend.REAL


@pytest.fixture(name="_model_target_backend")
def fixture_model_target_backend() -> VuforiaBackend:
    """Select the real policy without Model Target credential lookup."""
    return VuforiaBackend.REAL


@pytest.fixture(
    name="base_vws_url",
    params=[
        "https://vws.vuforia.com",
        "https://cloudreco.vuforia.com",
        "http://consumer.example",
    ],
)
def fixture_base_vws_url(*, request: pytest.FixtureRequest) -> str:
    """Supply canonical and custom URLs for controlled requests."""
    url = request.param
    assert isinstance(url, str)
    return url


@pytest.fixture(
    name="request_timeout",
    params=[RequestsTimeout, ConnectTimeout, ReadTimeout],
)
def fixture_request_timeout(
    *, request: pytest.FixtureRequest
) -> RequestsTimeout:
    """Supply a controlled base or derived timeout exception."""
    timeout_type = request.param
    assert isinstance(timeout_type, type)
    assert issubclass(timeout_type, RequestsTimeout)
    return timeout_type("Controlled timeout")


@pytest.fixture(name="timing_out_endpoint", params=[False, True])
def fixture_timing_out_endpoint(
    *,
    request: pytest.FixtureRequest,
    base_vws_url: str,
) -> Endpoint | ModelTargetEndpoint:
    """A shared endpoint which is sent through the controlled
    transport.
    """
    is_model_target = request.param
    assert isinstance(is_model_target, bool)
    if is_model_target:
        return ModelTargetEndpoint(
            base_url=base_vws_url,
            path_url="/modeltargets/datasets",
            method=HTTPMethod.GET,
            headers={},
            data=b"",
            takes_json_body=False,
        )
    return Endpoint(
        base_url=base_vws_url,
        path_url="/targets",
        method=HTTPMethod.GET,
        headers={},
        data=b"",
        successful_headers_result_code=None,
        successful_headers_status_code=HTTPStatus.OK,
        access_key="mock-access-key",
        secret_key="mock-secret-key",
    )


@pytest.fixture(autouse=True)
def fixture_controlled_transport(
    *,
    monkeypatch: pytest.MonkeyPatch,
    request_timeout: RequestsTimeout,
) -> Generator[None]:
    """Isolate setup and transport from real accounts and requests.

    Yields:
        ``None``, while the controlled transport is installed.
    """

    def send_timeout(
        session: requests.Session,
        *,
        request: requests.PreparedRequest,
        timeout: int,
    ) -> requests.Response:
        """Raise the controlled timeout instead of sending a request."""
        del session, request, timeout
        raise request_timeout

    def no_targets(client: VWS) -> list[str]:
        """Avoid real-service calls during database cleanup."""
        del client
        return []

    monkeypatch.setattr(
        target=requests.Session, name="send", value=send_timeout
    )
    monkeypatch.setattr(target=VWS, name="list_targets", value=no_targets)
    monkeypatch.setattr(
        target=vuforia_backends,
        name="get_real_cloud_database",
        value=CloudDatabase,
    )
    monkeypatch.setattr(
        target=vuforia_backends,
        name="get_real_inactive_cloud_database",
        value=lambda: CloudDatabase(state=States.PROJECT_INACTIVE),
    )
    monkeypatch.setattr(
        target=vuforia_backends,
        name="get_real_vumark_database",
        value=lambda: VuMarkCloudDatabase(
            target_manager_database_name="mock-vumark",
            server_access_key="mock-vumark-access",
            server_secret_key="mock-vumark-secret",
            target_id="mock-target",
            processing_target_id="mock-processing-target",
        ),
    )
    monkeypatch.setattr(
        target=vuforia_backends,
        name="get_real_inactive_vumark_database",
        value=lambda: InactiveVuMarkCloudDatabase(
            target_manager_database_name="mock-inactive-vumark",
            server_access_key="mock-inactive-vumark-access",
            server_secret_key="mock-inactive-vumark-secret",
        ),
    )
    handle_request_timeout(
        url="https://vws.vuforia.com/targets", error=request_timeout
    )
    yield
    # Backend fixtures finish first, restoring the strict default.
    handle_request_timeout(
        url="https://vws.vuforia.com/targets", error=request_timeout
    )


def test_default_propagates_timeouts(
    *,
    timing_out_endpoint: Endpoint | ModelTargetEndpoint,
    request_timeout: RequestsTimeout,
) -> None:
    """A host name alone never changes the strict shared timeout
    behavior.
    """
    with pytest.raises(expected_exception=RequestsTimeout) as exc:
        _ = timing_out_endpoint.send()
    assert exc.value is request_timeout


@pytest.mark.usefixtures("verify_mock_vuforia")
def test_real_vws_adapter_skips_timeouts(
    *, timing_out_endpoint: Endpoint | ModelTargetEndpoint
) -> None:
    """The real VWS setup installs the timeout policy for supplied
    URLs.
    """
    with pytest.raises(
        expected_exception=pytest.skip.Exception,
        match=r"The real Vuforia service timed out\.",
    ):
        _ = timing_out_endpoint.send()


@pytest.mark.usefixtures("verify_model_target_mock_vuforia")
def test_real_model_target_adapter_skips_timeouts(
    *, timing_out_endpoint: Endpoint | ModelTargetEndpoint
) -> None:
    """The real Model Target setup installs the same timeout policy."""
    with pytest.raises(
        expected_exception=pytest.skip.Exception,
        match=r"The real Vuforia service timed out\.",
    ):
        _ = timing_out_endpoint.send()


def test_nested_timeout_handlers(*, request_timeout: RequestsTimeout) -> None:
    """Nested policies restore the outer handler and finally the
    default.
    """
    calls: list[str] = []

    def outer_handler(*, url: str, error: RequestsTimeout) -> None:
        """Record a timeout handled by the outer context."""
        assert url == "http://consumer.example/targets"
        assert error is request_timeout
        calls.append("outer")

    def inner_handler(*, url: str, error: RequestsTimeout) -> None:
        """Record a timeout handled by the inner context."""
        assert url == "http://consumer.example/targets"
        assert error is request_timeout
        calls.append("inner")

    url = "http://consumer.example/targets"
    with handling_request_timeouts(handler=outer_handler):
        handle_request_timeout(url=url, error=request_timeout)
        with handling_request_timeouts(handler=inner_handler):
            handle_request_timeout(url=url, error=request_timeout)
        handle_request_timeout(url=url, error=request_timeout)
    handle_request_timeout(url=url, error=request_timeout)
    assert calls == ["outer", "inner", "outer"]
