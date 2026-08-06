"""Validators for the VWS per-second request rate."""

import threading
from collections import deque
from collections.abc import Callable, Iterable, Mapping

from beartype import beartype

from mock_vws._database_matchers import (
    AnyDatabase,
    get_database_matching_server_keys,
)
from mock_vws.database import CloudDatabase

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
        self._request_times: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._time_function = time_function

    def validate(self, *, database: CloudDatabase) -> None:
        """Raise an error if the database's request rate is exhausted."""
        limit = database.requests_per_second_limit
        if limit is None:
            return

        with self._lock:
            now = self._time_function()
            request_times = self._request_times.setdefault(
                database.server_access_key,
                deque(),
            )
            window_start = now - _WINDOW_SECONDS
            while request_times and request_times[0] <= window_start:
                request_times.popleft()

            if len(request_times) >= limit:
                raise TooManyRequestsError

            request_times.append(now)

    def remove_database(self, *, database: CloudDatabase) -> None:
        """Discard request history for a removed database."""
        with self._lock:
            self._request_times.pop(database.server_access_key, None)


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
    """Apply the configured request rate to the matching cloud
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
        request_rate_limiter.validate(database=database)
