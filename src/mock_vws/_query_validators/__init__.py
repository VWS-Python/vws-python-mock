"""Input validators to use in the mock query API."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from beartype import beartype

from mock_vws._query_validators.multipart import (
    MultipartForm,
    parse_multipart,
)
from mock_vws.database import CloudDatabase

from .accept_header_validators import validate_accept_header
from .auth_validators import (
    validate_auth_header_exists,
    validate_auth_header_has_signature,
    validate_auth_header_number_of_parts,
    validate_authorization,
    validate_client_key_exists,
)
from .content_length_validators import (
    validate_content_length_header_is_int,
    validate_content_length_header_not_too_large,
    validate_content_length_header_not_too_small,
)
from .content_type_validators import validate_content_type_header
from .date_validators import (
    validate_date_format,
    validate_date_header_given,
    validate_date_in_range,
)
from .fields_validators import validate_extra_fields
from .header_size_validators import validate_header_lines_not_too_large
from .image_validators import (
    validate_image_dimensions,
    validate_image_field_given,
    validate_image_file_size,
    validate_image_format,
    validate_image_is_image,
)
from .include_target_data_validators import validate_include_target_data
from .num_results_validators import validate_max_num_results
from .project_state_validators import validate_project_state


@beartype
@dataclass(frozen=True, kw_only=True)
class ValidatedQuery:
    """What the validators learn about a query request which passes them.

    Args:
        database: The database which the request's client keys belong to.
        form: The parsed body of the request.

    Attributes:
        database: The database which the request's client keys belong to.
        form: The parsed body of the request.
    """

    database: CloudDatabase
    form: MultipartForm


@beartype
def run_query_validators(
    *,
    request_path: str,
    request_headers: Mapping[str, str],
    request_body: bytes,
    request_method: str,
    databases: Iterable[CloudDatabase],
) -> ValidatedQuery:
    """Run all validators.

    Vuforia reports one problem with a request even when the request has
    more than one. Which problem it reports is decided by the order of the
    validators here, so that order is the mock's record of Vuforia's error
    precedence, verified against the real service.

    NGINX rejects a request with an over-long header line before it reaches
    Vuforia, so that is checked first.

    The body is parsed once, after the ``Content-Type`` header which names
    its boundary has been validated, and the parsed form is shared by every
    validator which reads the body.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.

    Returns:
        The database which the request's client keys belong to, and the
        parsed body of the request.
    """
    validate_header_lines_not_too_large(request_headers=request_headers)
    validate_content_length_header_is_int(request_headers=request_headers)
    validate_content_length_header_not_too_large(
        request_headers=request_headers,
        request_body=request_body,
    )
    validate_content_length_header_not_too_small(
        request_headers=request_headers,
        request_body=request_body,
    )
    validate_auth_header_exists(request_headers=request_headers)
    validate_auth_header_number_of_parts(request_headers=request_headers)
    validate_auth_header_has_signature(request_headers=request_headers)
    validate_client_key_exists(
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
    validate_project_state(database=database)
    validate_accept_header(request_headers=request_headers)
    validate_date_header_given(request_headers=request_headers)
    validate_date_format(request_headers=request_headers)
    validate_date_in_range(request_headers=request_headers)
    validate_content_type_header(
        request_headers=request_headers,
        request_body=request_body,
    )
    form = parse_multipart(
        request_headers=request_headers,
        request_body=request_body,
    )
    validate_extra_fields(form=form)
    validate_image_field_given(form=form)
    validate_image_is_image(form=form)
    validate_image_format(form=form)
    validate_image_dimensions(form=form)
    validate_image_file_size(form=form)
    validate_max_num_results(form=form)
    validate_include_target_data(form=form)
    return ValidatedQuery(database=database, form=form)
