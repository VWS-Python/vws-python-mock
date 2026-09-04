"""Tests for retrying transient Model Target Web API failures.

The policy under test is what keeps a one-off gateway error from the
load balancer in front of the real Model Target Web API from failing
CI. It is exercised here rather than against a backend because the
whole point of it is what happens when a request fails in a way which
cannot be provoked on demand.
"""

import time
from collections.abc import Callable, Mapping
from http import HTTPMethod, HTTPStatus

import pytest
import requests
import responses
from beartype import beartype

from tests.mock_vws.utils import ModelTargetEndpoint
from tests.mock_vws.utils.model_target_retries import (
    MAXIMUM_BACKOFF_SECONDS,
    MODEL_TARGET_RETRY_ATTEMPTS,
    model_target_get,
    retrying_transient_real_backend_failures,
    send_with_transient_retries,
)

_URL = "https://vws.vuforia.com/modeltargets/datasets/uuid/dataset"


@beartype
def _response(
    *,
    status_code: HTTPStatus,
    headers: Mapping[str, str],
) -> requests.Response:
    """Return a response with the given status code and headers."""
    response = requests.Response()
    response.status_code = status_code
    response.url = _URL
    response.headers.update(headers)
    return response


@beartype
def _responder(
    *,
    status_codes: list[HTTPStatus],
    headers: Mapping[str, str],
) -> Callable[[], requests.Response]:
    """Return a callable which returns each status code in turn.

    Args:
        status_codes: The status code to return from each call, in
            order. The last one is returned by every later call.
        headers: The headers to give every response.

    Returns:
        A callable which sends a request, or rather pretends to.
    """
    remaining = list(status_codes)

    def send() -> requests.Response:
        """Return the next response."""
        status_code = remaining[0] if len(remaining) == 1 else remaining.pop(0)
        return _response(status_code=status_code, headers=headers)

    return send


@pytest.fixture(name="waits")
def fixture_waits(*, monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """The waits which the policy asks for, rather than takes.

    Returns:
        A list which each wait is appended to instead of being slept
        for.
    """
    waits: list[float] = []
    monkeypatch.setattr(target=time, name="sleep", value=waits.append)
    return waits


class TestRealBackend:
    """Tests for safe requests against the real backend."""

    @staticmethod
    def test_transient_response_is_retried(*, waits: list[float]) -> None:
        """A transient gateway response is followed by another attempt,
        and the response to that attempt is returned.
        """
        send = _responder(
            status_codes=[HTTPStatus.BAD_GATEWAY, HTTPStatus.OK],
            headers={},
        )

        with retrying_transient_real_backend_failures():
            response = send_with_transient_retries(
                method=HTTPMethod.GET,
                send=send,
            )

        assert response.status_code == HTTPStatus.OK
        assert len(waits) == 1

    @staticmethod
    @pytest.mark.parametrize(
        argnames="status_code",
        argvalues=[
            HTTPStatus.BAD_GATEWAY,
            HTTPStatus.SERVICE_UNAVAILABLE,
            HTTPStatus.GATEWAY_TIMEOUT,
        ],
    )
    def test_persistent_transient_response(
        *,
        status_code: HTTPStatus,
        waits: list[float],
    ) -> None:
        """Each transient status code is retried up to the attempt
        limit, and the last response is returned rather than hidden, so
        that the caller's assertion reports the real status and body.
        """
        attempts = 0

        def send() -> requests.Response:
            """Always fail with the transient status code."""
            nonlocal attempts
            attempts += 1
            return _response(status_code=status_code, headers={})

        with retrying_transient_real_backend_failures():
            response = send_with_transient_retries(
                method=HTTPMethod.GET,
                send=send,
            )

        assert response.status_code == status_code
        assert attempts == MODEL_TARGET_RETRY_ATTEMPTS
        assert len(waits) == MODEL_TARGET_RETRY_ATTEMPTS - 1

    @staticmethod
    def test_error_response_is_not_retried(*, waits: list[float]) -> None:
        """A response which came from Vuforia rather than from the
        gateway is returned as it is, however unsuccessful it is.
        """
        attempts = 0

        def send() -> requests.Response:
            """Reject the request as unauthorized."""
            nonlocal attempts
            attempts += 1
            return _response(status_code=HTTPStatus.UNAUTHORIZED, headers={})

        with retrying_transient_real_backend_failures():
            response = send_with_transient_retries(
                method=HTTPMethod.GET,
                send=send,
            )

        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert attempts == 1
        assert not waits

    @staticmethod
    @pytest.mark.parametrize(
        argnames="method",
        argvalues=[HTTPMethod.POST, HTTPMethod.DELETE],
    )
    def test_mutating_request_is_not_retried(
        *,
        method: HTTPMethod,
        waits: list[float],
    ) -> None:
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
            return _response(status_code=HTTPStatus.BAD_GATEWAY, headers={})

        with retrying_transient_real_backend_failures():
            response = send_with_transient_retries(method=method, send=send)

        assert response.status_code == HTTPStatus.BAD_GATEWAY
        assert attempts == 1
        assert not waits

    @staticmethod
    def test_transport_failure_is_retried(*, waits: list[float]) -> None:
        """A dropped connection is followed by another attempt."""
        responses_to_send: list[HTTPStatus | Exception] = [
            requests.exceptions.ConnectionError(),
            requests.exceptions.ReadTimeout(),
            HTTPStatus.OK,
        ]

        def send() -> requests.Response:
            """Fail twice, then succeed.

            Returns:
                A successful response, once the failures are exhausted.

            Raises:
                Exception: The next queued transport failure.
            """
            item = responses_to_send.pop(0)
            if isinstance(item, Exception):
                raise item
            return _response(status_code=item, headers={})

        with retrying_transient_real_backend_failures():
            response = send_with_transient_retries(
                method=HTTPMethod.GET,
                send=send,
            )

        assert response.status_code == HTTPStatus.OK
        assert len(waits) == MODEL_TARGET_RETRY_ATTEMPTS - 1

    @staticmethod
    def test_persistent_transport_failure(*, waits: list[float]) -> None:
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

        assert len(waits) == MODEL_TARGET_RETRY_ATTEMPTS - 1

    @staticmethod
    def test_backoff_grows(*, waits: list[float]) -> None:
        """Each wait is at least as long as the one before it, and no
        wait is longer than the maximum.
        """
        send = _responder(status_codes=[HTTPStatus.BAD_GATEWAY], headers={})

        with retrying_transient_real_backend_failures():
            send_with_transient_retries(method=HTTPMethod.GET, send=send)

        first_wait, second_wait = waits
        assert 1 <= first_wait < second_wait <= MAXIMUM_BACKOFF_SECONDS


class TestRetryAfter:
    """Tests for the ``Retry-After`` header."""

    @staticmethod
    def test_honored(*, waits: list[float]) -> None:
        """A ``Retry-After`` header in seconds is waited for."""
        send = _responder(
            status_codes=[HTTPStatus.SERVICE_UNAVAILABLE, HTTPStatus.OK],
            headers={"retry-after": "2"},
        )

        with retrying_transient_real_backend_failures():
            send_with_transient_retries(method=HTTPMethod.GET, send=send)

        assert waits == [2]

    @staticmethod
    def test_capped(*, waits: list[float]) -> None:
        """A ``Retry-After`` header which asks for a long wait is capped,
        so that a test cannot be paused for an unbounded time.
        """
        send = _responder(
            status_codes=[HTTPStatus.SERVICE_UNAVAILABLE, HTTPStatus.OK],
            headers={"Retry-After": "3600"},
        )

        with retrying_transient_real_backend_failures():
            send_with_transient_retries(method=HTTPMethod.GET, send=send)

        assert waits == [MAXIMUM_BACKOFF_SECONDS]

    @staticmethod
    def test_not_a_number_is_ignored(*, waits: list[float]) -> None:
        """A ``Retry-After`` header in the HTTP-date form is ignored, and
        the backoff is used instead.
        """
        send = _responder(
            status_codes=[HTTPStatus.SERVICE_UNAVAILABLE, HTTPStatus.OK],
            headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"},
        )

        with retrying_transient_real_backend_failures():
            send_with_transient_retries(method=HTTPMethod.GET, send=send)

        (wait,) = waits
        assert 1 <= wait <= MAXIMUM_BACKOFF_SECONDS


class TestMockBackends:
    """Tests for requests which do not go to the real backend."""

    @staticmethod
    def test_configured_failure_is_not_retried(*, waits: list[float]) -> None:
        """A 5xx response is returned immediately when the policy is not
        switched on.

        Tests which configure a mock to fail with a 5xx expect exactly
        that response, and expect it at once.
        """
        attempts = 0

        def send() -> requests.Response:
            """Fail with a transient status code."""
            nonlocal attempts
            attempts += 1
            return _response(status_code=HTTPStatus.BAD_GATEWAY, headers={})

        response = send_with_transient_retries(
            method=HTTPMethod.GET,
            send=send,
        )

        assert response.status_code == HTTPStatus.BAD_GATEWAY
        assert attempts == 1
        assert not waits

    @staticmethod
    def test_policy_is_switched_off_again(*, waits: list[float]) -> None:
        """The policy applies only within the context, so a mock backend
        test which runs after a real backend test is not affected.
        """
        with retrying_transient_real_backend_failures():
            pass

        send = _responder(status_codes=[HTTPStatus.BAD_GATEWAY], headers={})
        response = send_with_transient_retries(
            method=HTTPMethod.GET,
            send=send,
        )

        assert response.status_code == HTTPStatus.BAD_GATEWAY
        assert not waits


class TestSendRequests:
    """Tests for the request helpers which apply the policy."""

    @staticmethod
    @responses.activate
    def test_model_target_get(*, waits: list[float]) -> None:
        """``model_target_get`` retries a transient failure and returns
        the response to the next attempt.
        """
        responses.add(
            method=responses.GET,
            url=_URL,
            status=HTTPStatus.BAD_GATEWAY,
        )
        responses.add(
            method=responses.GET,
            url=_URL,
            status=HTTPStatus.OK,
            body=b"dataset",
        )

        with retrying_transient_real_backend_failures():
            response = model_target_get(
                url=_URL,
                headers={"Authorization": "Bearer token"},
                timeout=30,
            )

        assert response.status_code == HTTPStatus.OK
        assert response.content == b"dataset"
        assert len(waits) == 1

    @staticmethod
    @responses.activate
    def test_endpoint_send(*, waits: list[float]) -> None:
        """A ``GET`` endpoint retries a transient failure.

        This is the path which the cross-cutting Model Target endpoint
        tests take, and it is where a gateway failure has been seen.
        """
        responses.add(
            method=responses.GET,
            url=_URL,
            status=HTTPStatus.GATEWAY_TIMEOUT,
        )
        responses.add(
            method=responses.GET,
            url=_URL,
            status=HTTPStatus.UNAUTHORIZED,
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
        assert len(waits) == 1
