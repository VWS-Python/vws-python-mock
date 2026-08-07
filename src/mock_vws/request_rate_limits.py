"""Per-endpoint VWS request rate limits."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import NotRequired, Self, TypedDict

from beartype import beartype


@beartype
class RateLimitedEndpoint(Enum):
    """A group of VWS endpoints which share a request rate limit."""

    GET_TARGET = auto()
    GET_DUPLICATES = auto()
    LIST_TARGETS = auto()
    OTHER = auto()


@beartype
class RequestRateLimitDict(TypedDict):
    """A dictionary type which represents a single request rate limit."""

    max_requests: int
    window_seconds: float


@beartype
class RequestRateLimitsDict(TypedDict):
    """A dictionary type which represents per-endpoint rate limits."""

    other: NotRequired[RequestRateLimitDict | None]
    get_target: NotRequired[RequestRateLimitDict | None]
    get_duplicates: NotRequired[RequestRateLimitDict | None]
    list_targets: NotRequired[RequestRateLimitDict | None]


@beartype
@dataclass(eq=True, frozen=True, kw_only=True)
class RequestRateLimit:
    """A maximum number of requests within a rolling time window.

    Args:
        max_requests: The number of requests accepted within the window.
        window_seconds: The length of the rolling window, in seconds.
    """

    max_requests: int
    window_seconds: float

    def to_dict(self) -> RequestRateLimitDict:
        """Dump a rate limit to a dictionary which can be loaded as
        JSON.
        """
        return {
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds,
        }

    @classmethod
    def from_dict(cls, limit_dict: RequestRateLimitDict) -> Self:
        """Load a rate limit from a dictionary."""
        return cls(
            max_requests=limit_dict["max_requests"],
            window_seconds=limit_dict["window_seconds"],
        )


@beartype
def _limit_to_dict(
    *,
    limit: RequestRateLimit | None,
) -> RequestRateLimitDict | None:
    """Dump a rate limit, or ``None``, to a JSON-compatible value."""
    if limit is None:
        return None
    return limit.to_dict()


@beartype
def _limit_from_dict(
    *,
    limit_dict: RequestRateLimitDict | None,
) -> RequestRateLimit | None:
    """Load a rate limit from a dictionary, or ``None``."""
    if limit_dict is None:
        return None
    return RequestRateLimit.from_dict(limit_dict=limit_dict)


@beartype
@dataclass(eq=True, frozen=True, kw_only=True)
class RequestRateLimits:
    """Request rate limits for each group of VWS endpoints.

    Each limit is tracked separately, in the same way that the real Vuforia
    Web Services document separate limits per endpoint.
    Endpoints without their own limit share the ``other`` limit.
    A limit of ``None`` means that no limit is applied.

    Args:
        other: The limit for endpoints without their own limit.
        get_target: The limit for ``GET /targets/{target_id}`` requests.
        get_duplicates: The limit for ``GET /duplicates/{target_id}``
            requests.
        list_targets: The limit for ``GET /targets`` requests.
    """

    other: RequestRateLimit | None = None
    get_target: RequestRateLimit | None = None
    get_duplicates: RequestRateLimit | None = None
    list_targets: RequestRateLimit | None = None

    def for_endpoint(
        self,
        *,
        endpoint: RateLimitedEndpoint,
    ) -> tuple[RateLimitedEndpoint, RequestRateLimit] | None:
        """Return the limit which applies to an endpoint.

        Args:
            endpoint: The endpoint to get a limit for.

        Returns:
            The endpoint group which shares the limit, and the limit itself,
            or ``None`` if no limit applies.
        """
        endpoint_limits = {
            RateLimitedEndpoint.GET_TARGET: self.get_target,
            RateLimitedEndpoint.GET_DUPLICATES: self.get_duplicates,
            RateLimitedEndpoint.LIST_TARGETS: self.list_targets,
            RateLimitedEndpoint.OTHER: None,
        }
        limit = endpoint_limits[endpoint]
        if limit is not None:
            return (endpoint, limit)
        if self.other is not None:
            return (RateLimitedEndpoint.OTHER, self.other)
        return None

    def to_dict(self) -> RequestRateLimitsDict:
        """Dump rate limits to a dictionary which can be loaded as
        JSON.
        """
        return {
            "other": _limit_to_dict(limit=self.other),
            "get_target": _limit_to_dict(limit=self.get_target),
            "get_duplicates": _limit_to_dict(limit=self.get_duplicates),
            "list_targets": _limit_to_dict(limit=self.list_targets),
        }

    @classmethod
    def from_dict(cls, limits_dict: RequestRateLimitsDict) -> Self:
        """Load rate limits from a dictionary."""
        return cls(
            other=_limit_from_dict(limit_dict=limits_dict.get("other")),
            get_target=_limit_from_dict(
                limit_dict=limits_dict.get("get_target"),
            ),
            get_duplicates=_limit_from_dict(
                limit_dict=limits_dict.get("get_duplicates"),
            ),
            list_targets=_limit_from_dict(
                limit_dict=limits_dict.get("list_targets"),
            ),
        )


DOCUMENTED_REQUEST_RATE_LIMITS = RequestRateLimits(
    other=RequestRateLimit(max_requests=15, window_seconds=1.0),
    get_target=RequestRateLimit(max_requests=45, window_seconds=1.0),
    get_duplicates=RequestRateLimit(max_requests=10, window_seconds=1.0),
    list_targets=RequestRateLimit(max_requests=1, window_seconds=60.0),
)
"""The request rate limits documented by Vuforia.

These limits have not been verified against the real Vuforia Web Services,
and so they are not applied by default.
"""
