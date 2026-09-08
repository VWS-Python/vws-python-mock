"""A tracker of recent VWS requests, used to apply request rate limits."""

import threading
from collections import deque
from collections.abc import Callable

from beartype import beartype

from mock_vws.database import CloudDatabase
from mock_vws.request_rate_limits import (
    RateLimitedEndpoint,
    RequestRateLimit,
)

from .exceptions import TooManyRequestsError

_WINDOW_SECONDS = 1.0


@beartype
class RequestRateLimiter:
    """Track request times independently for each cloud database."""

    def __init__(
        self,
        *,
        time_function: Callable[[], float],
    ) -> None:
        """Initialize an empty rate limiter."""
        self._request_times: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()
        self._time_function = time_function

    def validate(
        self,
        *,
        database: CloudDatabase,
        endpoint: RateLimitedEndpoint,
    ) -> None:
        """Raise an error if a rate limit for the request is exhausted.

        Args:
            database: The database which the request is made against.
            endpoint: The endpoint group which the request belongs to.

        Raises:
            TooManyRequestsError: A limit which applies to the request has
                been reached.
        """
        # The ``requests_per_second_limit`` setting applies to every VWS
        # request made against the database, no matter which endpoint is
        # used, and so it has a bucket of its own.
        buckets: list[tuple[str, RequestRateLimit]] = []
        if database.requests_per_second_limit is not None:
            buckets.append(
                (
                    "ALL_ENDPOINTS",
                    RequestRateLimit(
                        max_requests=database.requests_per_second_limit,
                        window_seconds=_WINDOW_SECONDS,
                    ),
                )
            )

        if database.request_rate_limits is not None:
            endpoint_limit = database.request_rate_limits.for_endpoint(
                endpoint=endpoint,
            )
            if endpoint_limit is not None:
                (limit_endpoint, limit) = endpoint_limit
                buckets.append((limit_endpoint.name, limit))

        with self._lock:
            now = self._time_function()
            request_times_for_buckets: list[deque[float]] = []
            for bucket_name, limit in buckets:
                request_times = self._request_times.setdefault(
                    (database.server_access_key, bucket_name),
                    deque(),
                )
                window_start = now - limit.window_seconds
                while (
                    len(request_times) > 0 and request_times[0] <= window_start
                ):
                    _ = request_times.popleft()

                if len(request_times) >= limit.max_requests:
                    raise TooManyRequestsError

                request_times_for_buckets.append(request_times)

            for request_times in request_times_for_buckets:
                request_times.append(now)

    def remove_database(self, *, database: CloudDatabase) -> None:
        """Discard request history for a removed database."""
        with self._lock:
            self._request_times = {
                key: value
                for key, value in self._request_times.items()
                if key[0] != database.server_access_key
            }
