"""The request context which every services validator is given."""

from collections.abc import Mapping
from dataclasses import dataclass

from beartype import beartype

from mock_vws._database_matchers import AnyDatabase
from mock_vws.request_rate_limits import RateLimitedEndpoint

from .request_rate_limiter import RequestRateLimiter


@beartype
@dataclass(frozen=True, kw_only=True)
class ValidatorContext:
    """Everything which a services validator is given.

    A validator is chosen by the route it belongs to, so it never has to
    work out whether it applies to the request. The route's own facts are
    copied onto the context rather than being looked up again from the
    path and the method.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        database: The database which the request's server keys belong to.
        request_rate_limiter: The rate limiter tracking recent requests.
        mandatory_keys: Keys which the route requires in the request body.
        optional_keys: Keys which the route allows in the request body.
        rate_limited_endpoint: The group of endpoints which the route shares
            a request rate limit with.
        allowed_for_inactive_cloud_project: Whether the route works against
            an inactive cloud database.

    Attributes:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        database: The database which the request's server keys belong to.
        request_rate_limiter: The rate limiter tracking recent requests.
        mandatory_keys: Keys which the route requires in the request body.
        optional_keys: Keys which the route allows in the request body.
        rate_limited_endpoint: The group of endpoints which the route shares
            a request rate limit with.
        allowed_for_inactive_cloud_project: Whether the route works against
            an inactive cloud database.
    """

    request_path: str
    request_headers: Mapping[str, str]
    request_body: bytes
    database: AnyDatabase
    request_rate_limiter: RequestRateLimiter
    mandatory_keys: frozenset[str]
    optional_keys: frozenset[str]
    rate_limited_endpoint: RateLimitedEndpoint
    allowed_for_inactive_cloud_project: bool
