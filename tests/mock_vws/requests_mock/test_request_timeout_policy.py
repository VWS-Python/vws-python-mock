"""Tests for timeout handling supplied by backend adapters."""

from collections.abc import Generator

import pytest
from requests.exceptions import ConnectTimeout, ReadTimeout
from requests.exceptions import Timeout as RequestsTimeout

from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend
from tests.mock_vws.utils.request_timeout_policy import (
    handling_request_timeouts,
    propagating_request_timeouts,
)


@pytest.fixture(name="_model_target_backend")
def fixture_model_target_backend() -> VuforiaBackend:
    """Select the real policy without credential lookup or requests."""
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
    """Supply canonical and custom URLs for controlled timeouts."""
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


@pytest.fixture(autouse=True)
def fixture_check_timeout_policy_cleanup(
    *, request_timeout: RequestsTimeout
) -> Generator[None]:
    """Check the default before setup and after backend fixtures finish.

    Yields:
        ``None``, while the test and its backend fixtures run.
    """
    with (
        pytest.raises(expected_exception=RequestsTimeout),
        propagating_request_timeouts(url="https://vws.vuforia.com/targets"),
    ):
        raise request_timeout
    yield
    with (
        pytest.raises(expected_exception=RequestsTimeout),
        propagating_request_timeouts(url="https://vws.vuforia.com/targets"),
    ):
        raise request_timeout


def test_default_propagates_timeouts(
    *, base_vws_url: str, request_timeout: RequestsTimeout
) -> None:
    """A host name alone never changes the strict shared timeout
    behavior.
    """
    with (
        pytest.raises(expected_exception=RequestsTimeout) as exc,
        propagating_request_timeouts(url=f"{base_vws_url}/targets"),
    ):
        raise request_timeout
    assert exc.value is request_timeout


@pytest.mark.usefixtures("verify_model_target_mock_vuforia")
def test_real_adapter_skips_timeouts(
    *, base_vws_url: str, request_timeout: RequestsTimeout
) -> None:
    """The real adapter skips a timeout at any supplied URL."""
    with (
        pytest.raises(
            expected_exception=pytest.skip.Exception,
            match=r"The real Vuforia service timed out\.",
        ),
        propagating_request_timeouts(url=f"{base_vws_url}/targets"),
    ):
        raise request_timeout


def test_nested_timeout_handlers(*, request_timeout: RequestsTimeout) -> None:
    """Nested policies restore the outer handler after a raised
    exception.
    """
    calls: list[str] = []
    url = "http://consumer.example/targets"

    def outer_handler(*, url: str, error: RequestsTimeout) -> None:
        """Record a timeout handled by the outer context."""
        assert url == "http://consumer.example/targets"
        assert error is request_timeout
        calls.append("outer")

    def inner_handler(*, url: str, error: RequestsTimeout) -> None:
        """Skip a timeout handled by the inner context."""
        assert url == "http://consumer.example/targets"
        assert error is request_timeout
        calls.append("inner")
        pytest.skip(reason="Controlled inner timeout")

    with handling_request_timeouts(handler=outer_handler):
        with (
            pytest.raises(expected_exception=RequestsTimeout) as exc,
            propagating_request_timeouts(url=url),
        ):
            raise request_timeout
        assert exc.value is request_timeout
        with (
            pytest.raises(
                expected_exception=pytest.skip.Exception,
                match="Controlled inner timeout",
            ),
            handling_request_timeouts(handler=inner_handler),
            propagating_request_timeouts(url=url),
        ):
            raise request_timeout
        with (
            pytest.raises(expected_exception=RequestsTimeout),
            propagating_request_timeouts(url=url),
        ):
            raise request_timeout
    with (
        pytest.raises(expected_exception=RequestsTimeout),
        propagating_request_timeouts(url=url),
    ):
        raise request_timeout
    assert calls == ["outer", "inner", "outer"]
