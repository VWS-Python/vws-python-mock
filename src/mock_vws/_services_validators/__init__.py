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
from .header_size_validators import validate_header_lines_not_too_large
from .routes import match_route


@beartype
def run_services_validators[DatabaseT: AnyDatabase](
    *,
    request_path: str,
    request_headers: Mapping[str, str],
    request_body: bytes,
    request_method: str,
    databases: Iterable[DatabaseT],
) -> DatabaseT:
    """Run the validators which apply to the request.

    Header size and authentication checks run before the route's ordered
    validators, which are given the matching VuMark database.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.

    Returns:
        The database which the request's server keys belong to.
    """
    validate_header_lines_not_too_large(request_headers=request_headers)
    validate_auth_header_exists(request_headers=request_headers)
    validate_auth_header_has_signature(request_headers=request_headers)
    _ = validate_access_key_exists(
        request_headers=request_headers, databases=databases
    )
    route = match_route(
        request_path=request_path,
        request_method=request_method,
    )
    database = validate_authorization(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )

    context = ValidatorContext(
        request_path=request_path,
        request_headers=request_headers,
        request_body=request_body,
        database=database,
        mandatory_keys=route.mandatory_keys,
        optional_keys=route.optional_keys,
    )
    for validator in route.validators:
        validator(context=context)

    return database
