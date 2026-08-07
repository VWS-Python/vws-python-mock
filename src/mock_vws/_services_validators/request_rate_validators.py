"""Validators for the VWS request rates."""

import re
import threading
from collections import deque
from collections.abc import Callable, Iterable, Mapping
from http import HTTPMethod

from beartype import beartype

from mock_vws._database_matchers import (
    AnyDatabase,
    get_database_matching_server_keys,
)
from mock_vws.database import CloudDatabase
from mock_vws.request_rate_limits import (
    RateLimitedEndpoint,
    RequestRateLimit,
)

from .exceptions import TooManyRequestsError

_WINDOW_SECONDS = 1.0

_GET_TARGET_PATH_PATTERN = re.compile(pattern=r"^/targets/[^/]+$")
_GET_DUPLICATES_PATH_PATTERN = re.compile(pattern=r"^/duplicates/[^/]+$")


@beartype
def _rate_limited_endpoint(
    *,
    request_method: str,
    request_path: str,
) -> RateLimitedEndpoint:
    """Return the endpoint group which a request belongs to."""
    path = request_path.split(sep="?", maxsplit=1)[0]
    if request_method == HTTPMethod.GET:
        if path == "/targets":
            return RateLimitedEndpoint.LIST_TARGETS
        if _GET_TARGET_PATH_PATTERN.fullmatch(string=path):
            return RateLimitedEndpoint.GET_TARGET
        if _GET_DUPLICATES_PATH_PATTERN.fullmatch(string=path):
            return RateLimitedEndpoint.GET_DUPLICATES
    return RateLimitedEndpoint.OTHER


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
                while request_times and request_times[0] <= window_start:
                    request_times.popleft()

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


@beartype
def validate_request_rate(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
    request_method: str,
    request_path: str,
    databases: Iterable[AnyDatabase],
    request_rate_limiter: RequestRateLimiter,
) -> None:
    """Apply the configured request rates to the matching cloud
    database.
    """
    database = get_database_matching_server_keys(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )
    if isinstance(database, CloudDatabase):
        endpoint = _rate_limited_endpoint(
            request_method=request_method,
            request_path=request_path,
        )
        request_rate_limiter.validate(database=database, endpoint=endpoint)
