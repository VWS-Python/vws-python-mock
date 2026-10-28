"""The transport for requests which no VWS route serves."""

from dataclasses import dataclass
from http import HTTPMethod
from typing import Protocol, runtime_checkable

from beartype import beartype


@beartype
@dataclass(frozen=True, kw_only=True)
class UnroutedResponse:
    """The parts of a response to a request which no route serves."""

    status_code: int
    body: bytes
    content_type: str | None
    content_encoding: str | None
    upstream_service_time: str | None


@runtime_checkable
class SendUnroutedRequest(Protocol):
    """A backend operation which sends a request outside its routes."""

    def __call__(
        self,
        *,
        method: HTTPMethod,
        request_path: str,
        headers: dict[str, str],
    ) -> UnroutedResponse | None:
        """Send the request and return its response, or ``None`` if
        the connection is refused.

        Args:
            method: The HTTP method to send.
            request_path: The path to request on the VWS service.
            headers: The request headers, including its authorization.
        """
        ...


@beartype
@dataclass(frozen=True, kw_only=True)
class UnroutedRequests:
    """The request operation and expected transport behavior.

    ``returns_response`` says whether the transport serves unmatched
    requests. A selective HTTP mock refuses them; a server returns a
    response. Shared tests assert the declared behavior in either case.
    """

    send: SendUnroutedRequest
    returns_response: bool
