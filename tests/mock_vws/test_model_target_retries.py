"""Tests for retrying transient Model Target Web API failures.

``tenacity`` does the retrying; these tests cover the policy decisions
layered on it, which cannot be provoked against a backend on demand.
"""

from http import HTTPMethod, HTTPStatus

import pytest
import requests
import responses
from beartype import beartype
from tenacity import Retrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_none

from tests.mock_vws.fixtures.real_model_target_retries import (
    MODEL_TARGET_RETRY_ATTEMPTS,
    REAL_MODEL_TARGET_RETRY_POLICY,
)
from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend
from tests.mock_vws.utils import ModelTargetEndpoint
from tests.mock_vws.utils.model_target_retries import (
    model_target_get,
    retrying_model_target_requests,
    send_with_transient_retries,
)

_URL = "https://vws.vuforia.com/modeltargets/datasets/uuid/dataset"


@beartype
def _response(*, status_code: HTTPStatus) -> requests.Response:
    """Return a response with the given status code."""
    response = requests.Response()
    response.status_code = status_code
    return response


@pytest.fixture(name="retry_policy")
def fixture_retry_policy() -> Retrying:
    """Use the real retry criteria without waiting between attempts."""
    return REAL_MODEL_TARGET_RETRY_POLICY.copy(wait=wait_none())


@pytest.fixture(name="_model_target_backend")
def fixture_model_target_backend() -> VuforiaBackend:
    """Select the real policy without credential lookup or requests."""
    return VuforiaBackend.REAL


def test_transient_response_is_retried(*, retry_policy: Retrying) -> None:
    """A transient gateway response is followed by another attempt,
    and the response to that attempt is returned.
    """
    remaining = [HTTPStatus.BAD_GATEWAY, HTTPStatus.OK]

    with retrying_model_target_requests(retrying=retry_policy):
        response = send_with_transient_retries(
            method=HTTPMethod.GET,
            send=lambda: _response(status_code=remaining.pop(0)),
        )

    assert response.status_code == HTTPStatus.OK


def test_persistent_transient_response(*, retry_policy: Retrying) -> None:
    """The last response is returned rather than hidden, so that the
    caller's assertion reports the real status and body.
    """
    attempts = 0

    def send() -> requests.Response:
        """Always fail with a transient status code."""
        nonlocal attempts
        attempts += 1
        return _response(status_code=HTTPStatus.SERVICE_UNAVAILABLE)

    with retrying_model_target_requests(retrying=retry_policy):
        response = send_with_transient_retries(
            method=HTTPMethod.GET,
            send=send,
        )

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert attempts == MODEL_TARGET_RETRY_ATTEMPTS


def test_persistent_transport_failure(*, retry_policy: Retrying) -> None:
    """A transport failure on the last attempt is not swallowed."""

    def send() -> requests.Response:
        """Always drop the connection.

        Raises:
            ConnectionError: Always.
        """
        msg = "Connection aborted."
        raise requests.exceptions.ConnectionError(msg)

    with (
        retrying_model_target_requests(retrying=retry_policy),
        pytest.raises(
            expected_exception=requests.exceptions.ConnectionError,
            match=r"Connection aborted\.",
        ),
    ):
        _ = send_with_transient_retries(method=HTTPMethod.GET, send=send)


def test_error_response_is_not_retried(*, retry_policy: Retrying) -> None:
    """A response which came from Vuforia rather than from the
    gateway is returned as it is, however unsuccessful it is.
    """
    attempts = 0

    def send() -> requests.Response:
        """Reject the request as unauthorized."""
        nonlocal attempts
        attempts += 1
        return _response(status_code=HTTPStatus.UNAUTHORIZED)

    with retrying_model_target_requests(retrying=retry_policy):
        _ = send_with_transient_retries(method=HTTPMethod.GET, send=send)

    assert attempts == 1


def test_mutating_request_is_not_retried(*, retry_policy: Retrying) -> None:
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

    with retrying_model_target_requests(retrying=retry_policy):
        _ = send_with_transient_retries(method=HTTPMethod.POST, send=send)

    assert attempts == 1


def test_configured_failure_is_not_retried(*, retry_policy: Retrying) -> None:
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
    with retrying_model_target_requests(retrying=retry_policy):
        pass

    response = send_with_transient_retries(
        method=HTTPMethod.GET,
        send=send,
    )

    assert response.status_code == HTTPStatus.BAD_GATEWAY
    assert attempts == 1


@responses.activate
def test_endpoint_send(*, retry_policy: Retrying) -> None:
    """A ``GET`` endpoint retries a transient failure.

    This is the path which the cross-cutting Model Target endpoint tests
    take, and it is where a gateway failure has been seen.
    """
    gateway_response = responses.Response(
        method=responses.GET, url=_URL, status=HTTPStatus.BAD_GATEWAY
    )
    unauthorized_response = responses.Response(
        method=responses.GET, url=_URL, status=HTTPStatus.UNAUTHORIZED
    )
    assert responses.add(gateway_response) is gateway_response
    assert responses.add(unauthorized_response) is unauthorized_response
    endpoint = ModelTargetEndpoint(
        base_url="https://vws.vuforia.com",
        path_url="/modeltargets/datasets/uuid/dataset",
        method=HTTPMethod.GET,
        headers={},
        data=b"",
        takes_json_body=False,
    )

    with retrying_model_target_requests(retrying=retry_policy):
        response = endpoint.send()

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert gateway_response.call_count == 1
    assert unauthorized_response.call_count == 1


@responses.activate
def test_model_target_get(*, retry_policy: Retrying) -> None:
    """``model_target_get`` retries a transient failure."""
    gateway_response = responses.Response(
        method=responses.GET, url=_URL, status=HTTPStatus.GATEWAY_TIMEOUT
    )
    dataset_response = responses.Response(
        method=responses.GET, url=_URL, body=b"dataset"
    )
    assert responses.add(gateway_response) is gateway_response
    assert responses.add(dataset_response) is dataset_response

    with retrying_model_target_requests(retrying=retry_policy):
        response = model_target_get(url=_URL, headers={}, timeout=30)

    assert response.content == b"dataset"
    assert gateway_response.call_count == 1
    assert dataset_response.call_count == 1


@pytest.mark.usefixtures("verify_model_target_mock_vuforia")
def test_real_adapter_installs_retry_policy() -> None:
    """Real adapter setup installs its policy without account access."""
    remaining = [HTTPStatus.BAD_GATEWAY, HTTPStatus.OK]
    response = send_with_transient_retries(
        method=HTTPMethod.GET,
        send=lambda: _response(status_code=remaining.pop(0)),
    )
    assert response.status_code == HTTPStatus.OK
    assert not bool(remaining)


def test_nested_retry_policies() -> None:
    """Nested policies restore the outer policy after a raised
    exception.
    """
    outer = Retrying(
        retry=retry_if_exception_type(exception_types=ValueError),
        stop=stop_after_attempt(max_attempt_number=2),
        wait=wait_none(),
        reraise=True,
    )
    inner = outer.copy(
        retry=retry_if_exception_type(exception_types=KeyError),
    )
    error = ValueError("Controlled failure")
    response = _response(status_code=HTTPStatus.OK)
    remaining: list[ValueError | requests.Response] = [
        error,
        response,
        error,
        error,
        response,
        error,
    ]

    def send() -> requests.Response:
        """Return the next controlled response or raise its exception."""
        outcome = remaining.pop(0)
        if isinstance(outcome, ValueError):
            raise outcome
        return outcome

    with retrying_model_target_requests(retrying=outer):
        assert (
            send_with_transient_retries(method=HTTPMethod.GET, send=send)
            is response
        )
        with (
            pytest.raises(
                expected_exception=ValueError, match="Controlled failure"
            ) as exc,
            retrying_model_target_requests(retrying=inner),
        ):
            _ = send_with_transient_retries(method=HTTPMethod.GET, send=send)
        assert exc.value is error
        assert (
            send_with_transient_retries(method=HTTPMethod.GET, send=send)
            is response
        )
    with pytest.raises(
        expected_exception=ValueError, match="Controlled failure"
    ) as exc:
        _ = send_with_transient_retries(method=HTTPMethod.GET, send=send)
    assert exc.value is error
    assert not bool(remaining)
