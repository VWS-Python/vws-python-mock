"""Retrying transient failures from the real Model Target Web API.

The real Model Target Web API sits behind a load balancer which
occasionally answers a perfectly good request with a gateway error, or
drops the connection.  That has nothing to do with the contract under
test, so a bounded number of retries for requests which are safe to
repeat keeps a one-off gateway error from failing CI.

Only requests to the real backend are retried.  The mock backends
answer immediately, and some tests configure a mock to return a 5xx
deliberately, so retrying those would be both pointless and wrong.
The policy is therefore switched on for the duration of a test against
the real Model Target backend and is off at all other times.

Only ``GET`` requests are retried.  Repeating a dataset creation
``POST`` can create a second dataset and can consume the account's
Model Target training allowance, and the outcome of a repeat is
ambiguous, so mutating requests are sent exactly once.
"""

import contextlib
from collections.abc import Callable, Generator, Mapping
from http import HTTPMethod, HTTPStatus

import requests
from beartype import beartype
from tenacity import RetryCallState, Retrying
from tenacity.retry import retry_if_exception_type, retry_if_result
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential_jitter
from vws.response import Response

# Status codes which mean "the gateway could not get an answer from
# Vuforia", rather than "Vuforia answered, and this is the answer".
TRANSIENT_MODEL_TARGET_STATUS_CODES = frozenset(
    {
        HTTPStatus.BAD_GATEWAY,
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
    },
)

# Transport failures which mean the request may never have been
# answered.
TRANSIENT_MODEL_TARGET_EXCEPTIONS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
)

# The total number of times a safe request is sent, including the first
# attempt.  This is deliberately small: a persistent upstream failure
# must still fail the test quickly.
MODEL_TARGET_RETRY_ATTEMPTS = 3

# Whether requests are going to the real Model Target backend.
#
# This is a list, rather than a boolean, so that the context manager can
# set and unset it without a ``global`` statement, in the same way as
# the running in-memory mock is tracked in ``vuforia_backends``.
_REAL_BACKEND: list[None] = []


@contextlib.contextmanager
@beartype
def retrying_transient_real_backend_failures() -> Generator[None]:
    """Retry transient failures of safe requests sent within this
    context.

    Yields:
        ``None``, with the retry policy switched on.
    """
    _REAL_BACKEND.append(None)
    try:
        yield
    finally:
        _REAL_BACKEND.pop()


@beartype
def _is_transient(response: Response | requests.Response) -> bool:
    """Whether a response is a transient gateway failure."""
    return response.status_code in TRANSIENT_MODEL_TARGET_STATUS_CODES


@beartype
def _last_outcome(retry_state: RetryCallState) -> Response | requests.Response:
    """Give up with the outcome of the last attempt.

    A transient failure on the last attempt is not hidden: a response is
    returned as it is, so that the caller's assertion reports the real
    status and body, and a transport failure propagates.
    """
    assert retry_state.outcome is not None
    outcome: Response | requests.Response = retry_state.outcome.result()
    return outcome


_RETRYING = Retrying(
    retry=(
        retry_if_exception_type(
            exception_types=TRANSIENT_MODEL_TARGET_EXCEPTIONS,
        )
        | retry_if_result(predicate=_is_transient)
    ),
    stop=stop_after_attempt(max_attempt_number=MODEL_TARGET_RETRY_ATTEMPTS),
    wait=wait_exponential_jitter(initial=1, max=10),
    retry_error_callback=_last_outcome,
)


@beartype
def send_with_transient_retries[ResponseT: (Response, requests.Response)](
    *,
    method: str,
    send: Callable[[], ResponseT],
) -> ResponseT:
    """Send a Model Target request, retrying transient failures.

    The request is sent exactly once unless it is a ``GET`` sent while
    :py:func:`retrying_transient_real_backend_failures` is active.

    Args:
        method: The HTTP method of the request.
        send: A callable which sends the request and returns the
            response.

    Returns:
        The response to the last attempt.
    """
    retryable = bool(_REAL_BACKEND) and method == HTTPMethod.GET
    if not retryable:
        return send()

    return _RETRYING(send)


@beartype
def model_target_get(
    *,
    url: str,
    headers: Mapping[str, str],
    timeout: int,
) -> requests.Response:
    """Send a ``GET`` request to the Model Target Web API.

    Args:
        url: The URL to request.
        headers: The headers to send.
        timeout: The request timeout, in seconds.

    Returns:
        The response to the last attempt.
    """
    return send_with_transient_retries(
        method=HTTPMethod.GET,
        send=lambda: requests.get(
            url=url,
            headers=dict(headers),
            timeout=timeout,
        ),
    )
