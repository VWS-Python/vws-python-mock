"""
Input validators to use in the mock query API.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from mock_vws.database import VuforiaDatabase


def run_query_validators(
    request_path: str,
    request_headers: dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: set[VuforiaDatabase],
) -> None:
    """
    Run all validators.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.
    """
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
    validate_authorization(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )
    validate_project_state(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )
    validate_accept_header(request_headers=request_headers)
    validate_date_header_given(request_headers=request_headers)
    validate_date_format(request_headers=request_headers)
    validate_date_in_range(request_headers=request_headers)
    validate_content_type_header(
        request_headers=request_headers,
        request_body=request_body,
    )
    validate_extra_fields(
        request_headers=request_headers,
        request_body=request_body,
    )
    validate_image_field_given(
        request_headers=request_headers,
        request_body=request_body,
    )
    validate_image_is_image(
        request_headers=request_headers,
        request_body=request_body,
    )
    validate_image_format(
        request_headers=request_headers,
        request_body=request_body,
    )
    validate_image_dimensions(
        request_headers=request_headers,
        request_body=request_body,
    )
    validate_image_file_size(
        request_headers=request_headers,
        request_body=request_body,
    )
    validate_max_num_results(
        request_headers=request_headers,
        request_body=request_body,
    )
    validate_include_target_data(
        request_headers=request_headers,
        request_body=request_body,
    )
