"""Input validators to use in the mock."""

from collections.abc import Iterable, Mapping

from beartype import beartype

from mock_vws._database_matchers import AnyDatabase

from .auth_validators import (
    validate_access_key_exists,
    validate_auth_header_exists,
    validate_auth_header_has_signature,
    validate_authorization,
)
from .context import ValidatorContext
from .request_rate_limiter import RequestRateLimiter
from .routes import match_route


@beartype
def run_services_validators[DatabaseT: AnyDatabase](
    *,
    request_path: str,
    request_headers: Mapping[str, str],
    request_body: bytes,
    request_method: str,
    databases: Iterable[DatabaseT],
    request_rate_limiter: RequestRateLimiter,
) -> DatabaseT:
    """Run the validators which apply to the request.

    Every request is authorized first, because the validators which follow
    are given the database which the request's server keys belong to. Which
    validators follow, and in which order, is decided by the route the
    request was made to. See :py:mod:`mock_vws._services_validators.routes`.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.
        request_rate_limiter: The rate limiter tracking recent requests.

    Returns:
        The database which the request's server keys belong to.
    """
    validate_auth_header_exists(request_headers=request_headers)
    validate_auth_header_has_signature(request_headers=request_headers)
    validate_access_key_exists(
        request_headers=request_headers,
        databases=databases,
    )
    database = validate_authorization(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )

    route = match_route(
        request_path=request_path,
        request_method=request_method,
    )
    context = ValidatorContext(
        request_path=request_path,
        request_headers=request_headers,
        request_body=request_body,
        database=database,
        request_rate_limiter=request_rate_limiter,
        mandatory_keys=route.mandatory_keys,
        optional_keys=route.optional_keys,
        rate_limited_endpoint=route.rate_limited_endpoint,
        allowed_for_inactive_cloud_project=(
            route.allowed_for_inactive_cloud_project
        ),
    )
    for validator in route.validators:
        validator(context=context)

    return database
