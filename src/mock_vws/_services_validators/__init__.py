"""
Input validators to use in the mock.
"""

from mock_vws.database import VuforiaDatabase
from typing import Dict, List

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
from .content_type_validators import (
    validate_content_type_header_given,
)
from .key_validators import validate_keys
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
from .json_validators import validate_json
from .metadata_validators import (
    validate_metadata_encoding,
    validate_metadata_size,
    validate_metadata_type,
)
from .name_validators import (
    validate_name_characters_in_range,
    validate_name_length,
    validate_name_type,
)
from .project_state_validators import (
    validate_project_state,
)
from .target_validators import validate_target_id_exists
from .width_validators import validate_width

def run_services_validators(
    request_text: str,
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Run all validators.

    Args:
        request_text: The content of the request.
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
    validate_json(
        request_text=request_text,
        request_body=request_body,
        request_method=request_method,
    )
    validate_keys(
        request_text=request_text,
        request_path=request_path,
        request_method=request_method,
    )
    validate_metadata_type(request_text=request_text)
    validate_metadata_encoding(request_text=request_text)
    validate_metadata_size(request_text=request_text)
    validate_active_flag(request_text=request_text)
    validate_image_data_type(request_text=request_text)
    validate_image_encoding(request_text=request_text)
    validate_image_is_image(request_text=request_text)
    validate_image_format(request_text=request_text)
    validate_image_color_space(request_text=request_text)

    validate_image_size(request_text=request_text)

    validate_name_type(request_text=request_text)
    validate_name_length(request_text=request_text)
    validate_name_characters_in_range(
        request_text=request_text,
        request_method=request_method,
        request_path=request_path,
    )

    validate_width(request_text=request_text)
    validate_content_type_header_given(
        request_headers=request_headers,
        request_method=request_method,
    )

    validate_date_header_given(request_headers=request_headers)

    validate_date_format(request_headers=request_headers)
    validate_date_in_range(request_headers=request_headers)

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
