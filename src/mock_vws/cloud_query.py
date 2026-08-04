"""Public configuration types for the Vuforia Cloud Query API."""

from dataclasses import dataclass, field

from beartype import beartype


@beartype
@dataclass(frozen=True, kw_only=True)
class CloudQueryFailureResponse:
    """A failure response returned by the Cloud Query API mock.

    Args:
        status_code: The HTTP status code to return.
        headers: The HTTP response headers to return.
        body: The raw response body. String bodies are encoded as UTF-8 by
            the HTTP backend; byte bodies are returned unchanged.
    """

    status_code: int
    headers: dict[str, str] = field(default_factory=dict[str, str])
    body: str | bytes = b""
