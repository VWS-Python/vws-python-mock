"""Backend-supplied handling of request timeouts."""

import contextlib
from collections.abc import Generator
from typing import Protocol, runtime_checkable

from beartype import beartype
from requests.exceptions import Timeout as RequestsTimeout


@runtime_checkable
class RequestTimeoutHandler(Protocol):
    """A backend operation for a request which timed out."""

    def __call__(self, *, url: str, error: RequestsTimeout) -> None:
        """Handle a timeout before the shared sender propagates it."""
        ...


_TIMEOUT_HANDLERS: list[RequestTimeoutHandler] = []


@contextlib.contextmanager
@beartype
def handling_request_timeouts(
    *, handler: RequestTimeoutHandler
) -> Generator[None]:
    """Use the supplied timeout handler within this context.

    Yields:
        ``None``, with the supplied handler active.
    """
    _TIMEOUT_HANDLERS.append(handler)
    try:
        yield
    finally:
        _ = _TIMEOUT_HANDLERS.pop()


@contextlib.contextmanager
@beartype
def propagating_request_timeouts(*, url: str) -> Generator[None]:
    """Apply the active policy to timeouts raised by a request.

    Yields:
        ``None``, while the request runs.
    """
    try:
        yield
    except RequestsTimeout as error:
        if bool(_TIMEOUT_HANDLERS):
            _TIMEOUT_HANDLERS[-1](url=url, error=error)
        raise
