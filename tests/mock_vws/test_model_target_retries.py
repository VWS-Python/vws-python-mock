"""Tests for retrying transient Model Target Web API failures.

``tenacity`` does the retrying; these tests cover the policy decisions
layered on it, which cannot be provoked against a backend on demand.
"""

import time
from http import HTTPMethod, HTTPStatus

import pytest
import requests
import responses
from beartype import beartype

from tests.mock_vws.utils import ModelTargetEndpoint
from tests.mock_vws.utils.model_target_retries import (
    MODEL_TARGET_RETRY_ATTEMPTS,
    model_target_get,
    retrying_transient_real_backend_failures,
    send_with_transient_retries,
)

_URL = "https://vws.vuforia.com/modeltargets/datasets/uuid/dataset"


@beartype
def _response(*, status_code: HTTPStatus) -> requests.Response:
    """Return a response with the given status code."""
    response = requests.Response()
    response.status_code = status_code
    return response


@beartype
def _do_not_sleep(seconds: float) -> None:
    """Do not sleep."""
    del seconds


@pytest.fixture(autouse=True, name="no_sleep")
def fixture_no_sleep(*, monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not wait between attempts."""
    monkeypatch.setattr(target=time, name="sleep", value=_do_not_sleep)


class TestRealBackend:
    """Tests for safe requests against the real backend."""

    @staticmethod
    def test_transient_response_is_retried() -> None:
        """A transient gateway response is followed by another attempt,
        and the response to that attempt is returned.
        """
        remaining = [HTTPStatus.BAD_GATEWAY, HTTPStatus.OK]

        with retrying_transient_real_backend_failures():
            response = send_with_transient_retries(
                method=HTTPMethod.GET,
                send=lambda: _response(status_code=remaining.pop(0)),
            )

        assert response.status_code == HTTPStatus.OK

    @staticmethod
    def test_persistent_transient_response() -> None:
        """The last response is returned rather than hidden, so that the
        caller's assertion reports the real status and body.
        """
        attempts = 0

        def send() -> requests.Response:
            """Always fail with a transient status code."""
            nonlocal attempts
            attempts += 1
            return _response(status_code=HTTPStatus.SERVICE_UNAVAILABLE)

        with retrying_transient_real_backend_failures():
            response = send_with_transient_retries(
                method=HTTPMethod.GET,
                send=send,
            )

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert attempts == MODEL_TARGET_RETRY_ATTEMPTS

    @staticmethod
    def test_persistent_transport_failure() -> None:
        """A transport failure on the last attempt is not swallowed."""

        def send() -> requests.Response:
            """Always drop the connection.

            Raises:
                ConnectionError: Always.
            """
            msg = "Connection aborted."
            raise requests.exceptions.ConnectionError(msg)

        with (
            retrying_transient_real_backend_failures(),
            pytest.raises(
                expected_exception=requests.exceptions.ConnectionError,
                match=r"Connection aborted\.",
            ),
        ):
            send_with_transient_retries(method=HTTPMethod.GET, send=send)

    @staticmethod
    def test_error_response_is_not_retried() -> None:
        """A response which came from Vuforia rather than from the
        gateway is returned as it is, however unsuccessful it is.
        """
        attempts = 0

        def send() -> requests.Response:
            """Reject the request as unauthorized."""
            nonlocal attempts
            attempts += 1
            return _response(status_code=HTTPStatus.UNAUTHORIZED)

        with retrying_transient_real_backend_failures():
            send_with_transient_retries(method=HTTPMethod.GET, send=send)

        assert attempts == 1

    @staticmethod
    def test_mutating_request_is_not_retried() -> None:
        """A request which is not safe to repeat is sent exactly once,
        even when it fails transiently.

        Repeating a dataset creation can create a second dataset and
        can consume the account's Model Target training allowance.
        """
        attempts = 0

        def send() -> requests.Response:
            """Fail with a transient status code."""
            nonlocal attempts
            attempts += 1
            return _response(status_code=HTTPStatus.BAD_GATEWAY)

        with retrying_transient_real_backend_failures():
            send_with_transient_retries(method=HTTPMethod.POST, send=send)

        assert attempts == 1


class TestMockBackends:
    """Tests for requests which do not go to the real backend."""

    @staticmethod
    def test_configured_failure_is_not_retried() -> None:
        """A 5xx response is returned immediately outside the context.

        Tests which configure a mock to fail with a 5xx expect exactly
        that response, and expect it at once.
        """
        attempts = 0

        def send() -> requests.Response:
            """Fail with a transient status code."""
            nonlocal attempts
            attempts += 1
            return _response(status_code=HTTPStatus.BAD_GATEWAY)

        # Enter and leave the context first, to check it is switched off
        # again for a mock backend test which runs after a real one.
        with retrying_transient_real_backend_failures():
            pass

        response = send_with_transient_retries(
            method=HTTPMethod.GET,
            send=send,
        )

        assert response.status_code == HTTPStatus.BAD_GATEWAY
        assert attempts == 1


@responses.activate
def test_endpoint_send() -> None:
    """A ``GET`` endpoint retries a transient failure.

    This is the path which the cross-cutting Model Target endpoint tests
    take, and it is where a gateway failure has been seen.
    """
    responses.add(
        method=responses.GET, url=_URL, status=HTTPStatus.BAD_GATEWAY
    )
    responses.add(
        method=responses.GET, url=_URL, status=HTTPStatus.UNAUTHORIZED
    )
    endpoint = ModelTargetEndpoint(
        base_url="https://vws.vuforia.com",
        path_url="/modeltargets/datasets/uuid/dataset",
        method=HTTPMethod.GET,
        headers={},
        data=b"",
        takes_json_body=False,
    )

    with retrying_transient_real_backend_failures():
        response = endpoint.send()

    assert response.status_code == HTTPStatus.UNAUTHORIZED


@responses.activate
def test_model_target_get() -> None:
    """``model_target_get`` retries a transient failure."""
    responses.add(
        method=responses.GET, url=_URL, status=HTTPStatus.GATEWAY_TIMEOUT
    )
    responses.add(method=responses.GET, url=_URL, body=b"dataset")

    with retrying_transient_real_backend_failures():
        response = model_target_get(url=_URL, headers={}, timeout=30)

    assert response.content == b"dataset"
