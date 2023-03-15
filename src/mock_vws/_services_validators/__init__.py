"""
Input validators to use in the mock.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .active_flag_validators import validate_active_flag
from .auth_validators import (
    validate_access_key_exists,
    validate_auth_header_exists,
    validate_auth_header_has_signature,
    validate_authorization,
)
from .content_length_validators import (
    validate_content_length_header_is_int,
    validate_content_length_header_not_too_large,
    validate_content_length_header_not_too_small,
)
from .content_type_validators import validate_content_type_header_given
from .date_validators import (
    validate_date_format,
    validate_date_header_given,
    validate_date_in_range,
)
from .image_validators import (
    validate_image_color_space,
    validate_image_data_type,
    validate_image_encoding,
    validate_image_format,
    validate_image_is_image,
    validate_image_size,
)
from .json_validators import validate_body_given, validate_json
from .key_validators import validate_keys
from .metadata_validators import (
    validate_metadata_encoding,
    validate_metadata_size,
    validate_metadata_type,
)
from .name_validators import (
    validate_name_characters_in_range,
    validate_name_does_not_exist_existing_target,
    validate_name_does_not_exist_new_target,
    validate_name_length,
    validate_name_type,
)
from .project_state_validators import validate_project_state
from .target_validators import validate_target_id_exists
from .width_validators import validate_width

if TYPE_CHECKING:
    from mock_vws.database import VuforiaDatabase


def run_services_validators(
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
    validate_auth_header_exists(request_headers=request_headers)
    validate_auth_header_has_signature(request_headers=request_headers)
    validate_access_key_exists(
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
    validate_target_id_exists(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )

    validate_body_given(
        request_body=request_body,
        request_method=request_method,
    )

    validate_date_header_given(request_headers=request_headers)
    validate_date_format(request_headers=request_headers)
    validate_date_in_range(request_headers=request_headers)

    validate_json(request_body=request_body)

    validate_keys(
        request_body=request_body,
        request_path=request_path,
        request_method=request_method,
    )
    validate_metadata_type(request_body=request_body)
    validate_metadata_encoding(request_body=request_body)
    validate_metadata_size(request_body=request_body)
    validate_active_flag(request_body=request_body)

    validate_image_data_type(request_body=request_body)
    validate_image_encoding(request_body=request_body)
    validate_image_is_image(request_body=request_body)
    validate_image_format(request_body=request_body)
    validate_image_color_space(request_body=request_body)
    validate_image_size(request_body=request_body)

    validate_name_type(request_body=request_body)
    validate_name_length(request_body=request_body)
    validate_name_characters_in_range(
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
    )
    validate_name_does_not_exist_new_target(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )
    validate_name_does_not_exist_existing_target(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )

    validate_width(request_body=request_body)
    validate_content_type_header_given(
        request_headers=request_headers,
        request_method=request_method,
    )

    validate_content_length_header_is_int(
        request_headers=request_headers,
        request_body=request_body,
    )
    validate_content_length_header_not_too_large(
        request_headers=request_headers,
        request_body=request_body,
    )

    validate_content_length_header_not_too_small(
        request_headers=request_headers,
        request_body=request_body,
    )
