"""Apply retry policies supplied by Model Target backend adapters.

Requests are sent once by default. An adapter can install a scoped retry
policy for GET requests; mutating requests are always sent exactly once.
"""

import contextlib
from collections.abc import Callable, Generator, Mapping
from http import HTTPMethod

import requests
from beartype import beartype
from tenacity import Retrying
from vws.response import Response

_RETRY_POLICIES: list[Retrying] = []


@contextlib.contextmanager
@beartype
def retrying_model_target_requests(*, retrying: Retrying) -> Generator[None]:
    """Use the supplied retry policy for safe requests within this context.

    Yields:
        ``None``, with the supplied policy active.
    """
    _RETRY_POLICIES.append(retrying)
    try:
        yield
    finally:
        _ = _RETRY_POLICIES.pop()


@beartype
def send_with_transient_retries[ResponseT: (Response, requests.Response)](
    *,
    method: str,
    send: Callable[[], ResponseT],
) -> ResponseT:
    """Send a Model Target request, retrying transient failures.

    The request is sent exactly once unless it is a ``GET`` sent while
    :py:func:`retrying_model_target_requests` is active.

    Args:
        method: The HTTP method of the request.
        send: A callable which sends the request and returns the
            response.

    Returns:
        The response to the last attempt.
    """
    retryable = bool(_RETRY_POLICIES) and method == HTTPMethod.GET
    if not retryable:
        return send()

    return _RETRY_POLICIES[-1](send)


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
