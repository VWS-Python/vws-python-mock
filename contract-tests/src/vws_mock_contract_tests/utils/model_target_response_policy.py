"""Backend-supplied handling of unexpected Model Target responses."""

import contextlib
from collections.abc import Generator
from typing import Protocol, runtime_checkable

import requests
from beartype import beartype
from vws.response import Response


@runtime_checkable
class ModelTargetResponseHandler(Protocol):
    """A backend operation for an unexpected Model Target response."""

    def __call__(self, *, response: Response | requests.Response) -> None:
        """Handle the response before the shared assertion reports it."""
        ...


_RESPONSE_HANDLERS: list[ModelTargetResponseHandler] = []


@contextlib.contextmanager
@beartype
def handling_unexpected_model_target_responses(
    *,
    handler: ModelTargetResponseHandler,
) -> Generator[None]:
    """Use the supplied response handler within this context.

    Yields:
        ``None``, with the supplied handler active.
    """
    _RESPONSE_HANDLERS.append(handler)
    try:
        yield
    finally:
        _ = _RESPONSE_HANDLERS.pop()


@beartype
def handle_unexpected_model_target_response(
    *,
    response: Response | requests.Response,
) -> None:
    """Notify the backend before asserting an unexpected status."""
    if bool(_RESPONSE_HANDLERS):
        _RESPONSE_HANDLERS[-1](response=response)
