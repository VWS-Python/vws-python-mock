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
import secrets
import time
from collections.abc import Callable, Generator, Mapping
from http import HTTPMethod, HTTPStatus

import requests
from beartype import beartype
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

_FIRST_BACKOFF_SECONDS = 1.0
# The longest this policy waits between two attempts, whether the wait
# comes from the backoff or from a ``Retry-After`` header.
MAXIMUM_BACKOFF_SECONDS = 10.0
# The fraction of the backoff which is randomized, so that requests
# from concurrent CI jobs do not line up on the same retry instant.
_JITTER_FRACTION = 0.25
_JITTER_RESOLUTION = 1000

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
def _retry_after_seconds(*, headers: Mapping[str, str]) -> float | None:
    """The wait asked for by a ``Retry-After`` header, if it is usable.

    Only the delay-seconds form is honored.  The HTTP-date form is not,
    because nothing has been observed sending it and a wrong reading of
    it could pause a test for a long time.

    Args:
        headers: The headers of the response.

    Returns:
        The number of seconds to wait, capped at
        :py:data:`MAXIMUM_BACKOFF_SECONDS`, or ``None`` if the header is
        absent or is not a usable number of seconds.
    """
    values = [
        value
        for key, value in headers.items()
        if str.lower(key) == "retry-after"
    ]
    if not values:
        return None

    (value,) = values
    if not str.isdigit(str.strip(value)):
        return None

    return min(float(value), MAXIMUM_BACKOFF_SECONDS)


@beartype
def _backoff_seconds(*, attempt: int) -> float:
    """The wait after a given attempt, with jitter.

    Args:
        attempt: The number of the attempt which just failed, counting
            from one.

    Returns:
        The number of seconds to wait before the next attempt.
    """
    growth: float = 2 ** (attempt - 1)
    unjittered = min(
        _FIRST_BACKOFF_SECONDS * growth,
        MAXIMUM_BACKOFF_SECONDS,
    )
    jitter_multiplier = (
        secrets.randbelow(exclusive_upper_bound=_JITTER_RESOLUTION)
        / _JITTER_RESOLUTION
    )
    return unjittered * (1 + _JITTER_FRACTION * jitter_multiplier)


@beartype
def send_with_transient_retries[ResponseT: (Response, requests.Response)](
    *,
    method: str,
    send: Callable[[], ResponseT],
) -> ResponseT:
    """Send a Model Target request, retrying transient failures.

    The request is sent exactly once unless it is a ``GET`` sent while
    :py:func:`retrying_transient_real_backend_failures` is active.

    A transient failure on the last attempt is not hidden: the response
    is returned as it is, so that the caller's assertion reports the
    real status and body, and a transport failure propagates.

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

    for attempt in range(1, MODEL_TARGET_RETRY_ATTEMPTS):
        try:
            response = send()
        except TRANSIENT_MODEL_TARGET_EXCEPTIONS:
            time.sleep(_backoff_seconds(attempt=attempt))
            continue

        if response.status_code not in TRANSIENT_MODEL_TARGET_STATUS_CODES:
            return response

        wait_seconds = _retry_after_seconds(headers=response.headers)
        if wait_seconds is None:
            wait_seconds = _backoff_seconds(attempt=attempt)
        time.sleep(wait_seconds)

    return send()


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
