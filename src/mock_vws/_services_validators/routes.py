"""The VWS routes, and the validators which apply to each of them.

Vuforia reports one problem with a request even when the request has more
than one. Which problem it reports is decided by the order of the validators
in each route's chain, so that order is the mock's record of Vuforia's error
precedence, verified against the real service.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from http import HTTPMethod

from beartype import beartype

from mock_vws._mock_common import RECO_COUNTS_REPORT_PATH_PATTERN
from mock_vws.request_rate_limits import RateLimitedEndpoint

from .active_flag_validators import validate_active_flag
from .content_length_validators import (
    validate_content_length_header_is_int,
    validate_content_length_header_not_too_large,
    validate_content_length_header_not_too_small,
)
from .content_type_validators import validate_content_type_header_given
from .database_id_validators import validate_database_id_matches_keys
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
    validate_image_integrity,
    validate_image_is_image,
    validate_image_pixel_count,
    validate_image_size,
)
from .instance_id_validators import (
    validate_instance_id_not_empty,
    validate_instance_id_type,
)
from .json_validators import (
    validate_no_body_given,
    validate_reco_counts_report_json,
    validate_target_json,
    validate_vumark_instance_json,
)
from .key_validators import validate_keys
from .metadata_validators import (
    validate_metadata_encoding,
    validate_metadata_size,
    validate_metadata_type,
)
from .name_validators import (
    validate_existing_target_name_characters_in_range,
    validate_name_does_not_exist_existing_target,
    validate_name_does_not_exist_new_target,
    validate_name_length,
    validate_name_type,
    validate_new_target_name_characters_in_range,
)
from .project_state_validators import validate_project_state
from .request_quota_validators import validate_request_quota
from .request_rate_validators import validate_request_rate
from .target_quota_validators import validate_target_quota
from .target_validators import validate_target_id_exists
from .width_validators import validate_width

# The Flask app routes a target ID of any characters other than a slash, so
# the route table has to match the same paths that it does. The
# ``requests``-based mock serves only alphanumeric target IDs, and gives its
# own unrouted response for anything else.
_TARGET_ID_PATTERN = "[^/]+"


# A check which a request must pass before an endpoint runs. Every validator
# takes a
# :py:class:`~mock_vws._services_validators.context.ValidatorContext` as its
# ``context`` keyword argument, and raises a ``ValidatorError`` if the request
# is not valid.
type Validator = Callable[..., None]


@beartype
@dataclass(frozen=True, kw_only=True)
class Route:
    """A VWS route, and everything the validators need to know about it.

    Args:
        path_pattern: A pattern which matches the path of the route, and only
            the path of the route.
        http_method: The HTTP method of the route.
        mandatory_keys: Keys required in the request body.
        optional_keys: Keys which are not required in the request body but
            which are allowed.
        rate_limited_endpoint: The group of endpoints which the route shares a
            request rate limit with.
        allowed_for_inactive_cloud_project: Whether the route works against an
            inactive cloud database.
        validators: The validators which apply to the route, in the order in
            which they apply.

    Attributes:
        path_pattern: A pattern which matches the path of the route, and only
            the path of the route.
        http_method: The HTTP method of the route.
        mandatory_keys: Keys required in the request body.
        optional_keys: Keys which are not required in the request body but
            which are allowed.
        rate_limited_endpoint: The group of endpoints which the route shares a
            request rate limit with.
        allowed_for_inactive_cloud_project: Whether the route works against an
            inactive cloud database.
        validators: The validators which apply to the route, in the order in
            which they apply.
    """

    path_pattern: str
    http_method: HTTPMethod
    mandatory_keys: frozenset[str]
    optional_keys: frozenset[str]
    rate_limited_endpoint: RateLimitedEndpoint
    allowed_for_inactive_cloud_project: bool
    validators: Sequence[Validator]


# Every route is quota checked, rate limited and refused when the project is
# in a state which does not allow it.
_PROJECT_VALIDATORS: Sequence[Validator] = (
    validate_request_quota,
    validate_request_rate,
    validate_project_state,
)

_DATE_HEADER_VALIDATORS: Sequence[Validator] = (
    validate_date_header_given,
    validate_date_format,
    validate_date_in_range,
)

_CONTENT_LENGTH_HEADER_VALIDATORS: Sequence[Validator] = (
    validate_content_length_header_is_int,
    validate_content_length_header_not_too_large,
    validate_content_length_header_not_too_small,
)

_METADATA_VALIDATORS: Sequence[Validator] = (
    validate_metadata_type,
    validate_metadata_encoding,
    validate_metadata_size,
)

_IMAGE_VALIDATORS: Sequence[Validator] = (
    validate_image_data_type,
    validate_image_encoding,
    validate_image_is_image,
    validate_image_format,
    validate_image_color_space,
    validate_image_size,
    validate_image_pixel_count,
    validate_image_integrity,
)

_ADD_TARGET = Route(
    path_pattern="/targets",
    http_method=HTTPMethod.POST,
    mandatory_keys=frozenset({"image", "width", "name"}),
    optional_keys=frozenset({"active_flag", "application_metadata"}),
    rate_limited_endpoint=RateLimitedEndpoint.OTHER,
    allowed_for_inactive_cloud_project=False,
    validators=(
        *_PROJECT_VALIDATORS,
        validate_target_quota,
        *_DATE_HEADER_VALIDATORS,
        validate_target_json,
        validate_keys,
        *_METADATA_VALIDATORS,
        validate_active_flag,
        *_IMAGE_VALIDATORS,
        validate_name_type,
        validate_name_length,
        validate_new_target_name_characters_in_range,
        validate_name_does_not_exist_new_target,
        validate_width,
        validate_content_type_header_given,
        *_CONTENT_LENGTH_HEADER_VALIDATORS,
    ),
)

_UPDATE_TARGET = Route(
    path_pattern=f"/targets/{_TARGET_ID_PATTERN}",
    http_method=HTTPMethod.PUT,
    mandatory_keys=frozenset(),
    optional_keys=frozenset(
        {
            "active_flag",
            "application_metadata",
            "image",
            "name",
            "width",
        }
    ),
    rate_limited_endpoint=RateLimitedEndpoint.OTHER,
    allowed_for_inactive_cloud_project=False,
    validators=(
        *_PROJECT_VALIDATORS,
        validate_target_id_exists,
        *_DATE_HEADER_VALIDATORS,
        validate_target_json,
        validate_keys,
        *_METADATA_VALIDATORS,
        validate_active_flag,
        *_IMAGE_VALIDATORS,
        validate_name_type,
        validate_name_length,
        validate_existing_target_name_characters_in_range,
        validate_name_does_not_exist_existing_target,
        validate_width,
        validate_content_type_header_given,
        *_CONTENT_LENGTH_HEADER_VALIDATORS,
    ),
)

_DELETE_TARGET = Route(
    path_pattern=f"/targets/{_TARGET_ID_PATTERN}",
    http_method=HTTPMethod.DELETE,
    mandatory_keys=frozenset(),
    optional_keys=frozenset(),
    rate_limited_endpoint=RateLimitedEndpoint.OTHER,
    allowed_for_inactive_cloud_project=False,
    validators=(
        *_PROJECT_VALIDATORS,
        validate_target_id_exists,
        validate_no_body_given,
        *_DATE_HEADER_VALIDATORS,
        *_CONTENT_LENGTH_HEADER_VALIDATORS,
    ),
)

_DATABASE_SUMMARY = Route(
    path_pattern="/summary",
    http_method=HTTPMethod.GET,
    mandatory_keys=frozenset(),
    optional_keys=frozenset(),
    rate_limited_endpoint=RateLimitedEndpoint.OTHER,
    allowed_for_inactive_cloud_project=True,
    validators=(
        *_PROJECT_VALIDATORS,
        validate_no_body_given,
        *_DATE_HEADER_VALIDATORS,
        *_CONTENT_LENGTH_HEADER_VALIDATORS,
    ),
)

_TARGET_LIST = Route(
    path_pattern="/targets",
    http_method=HTTPMethod.GET,
    mandatory_keys=frozenset(),
    optional_keys=frozenset(),
    rate_limited_endpoint=RateLimitedEndpoint.LIST_TARGETS,
    allowed_for_inactive_cloud_project=True,
    validators=(
        *_PROJECT_VALIDATORS,
        validate_no_body_given,
        *_DATE_HEADER_VALIDATORS,
        *_CONTENT_LENGTH_HEADER_VALIDATORS,
    ),
)

_GET_TARGET = Route(
    path_pattern=f"/targets/{_TARGET_ID_PATTERN}",
    http_method=HTTPMethod.GET,
    mandatory_keys=frozenset(),
    optional_keys=frozenset(),
    rate_limited_endpoint=RateLimitedEndpoint.GET_TARGET,
    allowed_for_inactive_cloud_project=True,
    validators=(
        *_PROJECT_VALIDATORS,
        validate_target_id_exists,
        validate_no_body_given,
        *_DATE_HEADER_VALIDATORS,
        *_CONTENT_LENGTH_HEADER_VALIDATORS,
    ),
)

_TARGET_SUMMARY = Route(
    path_pattern=f"/summary/{_TARGET_ID_PATTERN}",
    http_method=HTTPMethod.GET,
    mandatory_keys=frozenset(),
    optional_keys=frozenset(),
    rate_limited_endpoint=RateLimitedEndpoint.OTHER,
    allowed_for_inactive_cloud_project=True,
    validators=(
        *_PROJECT_VALIDATORS,
        validate_target_id_exists,
        validate_no_body_given,
        *_DATE_HEADER_VALIDATORS,
        *_CONTENT_LENGTH_HEADER_VALIDATORS,
    ),
)

_GET_DUPLICATES = Route(
    path_pattern=f"/duplicates/{_TARGET_ID_PATTERN}",
    http_method=HTTPMethod.GET,
    mandatory_keys=frozenset(),
    optional_keys=frozenset(),
    rate_limited_endpoint=RateLimitedEndpoint.GET_DUPLICATES,
    allowed_for_inactive_cloud_project=False,
    validators=(
        *_PROJECT_VALIDATORS,
        validate_target_id_exists,
        validate_no_body_given,
        *_DATE_HEADER_VALIDATORS,
        *_CONTENT_LENGTH_HEADER_VALIDATORS,
    ),
)

_GENERATE_INSTANCE = Route(
    path_pattern=f"/targets/{_TARGET_ID_PATTERN}/instances",
    http_method=HTTPMethod.POST,
    mandatory_keys=frozenset({"instance_id"}),
    optional_keys=frozenset(),
    rate_limited_endpoint=RateLimitedEndpoint.OTHER,
    allowed_for_inactive_cloud_project=False,
    validators=(
        *_PROJECT_VALIDATORS,
        validate_target_id_exists,
        *_DATE_HEADER_VALIDATORS,
        validate_vumark_instance_json,
        validate_keys,
        validate_instance_id_type,
        validate_instance_id_not_empty,
        validate_content_type_header_given,
        *_CONTENT_LENGTH_HEADER_VALIDATORS,
    ),
)

_RECO_COUNTS_REPORT = Route(
    path_pattern=RECO_COUNTS_REPORT_PATH_PATTERN,
    http_method=HTTPMethod.POST,
    mandatory_keys=frozenset({"month"}),
    optional_keys=frozenset(),
    rate_limited_endpoint=RateLimitedEndpoint.OTHER,
    allowed_for_inactive_cloud_project=False,
    validators=(
        validate_database_id_matches_keys,
        *_PROJECT_VALIDATORS,
        *_DATE_HEADER_VALIDATORS,
        validate_reco_counts_report_json,
        validate_keys,
        validate_content_type_header_given,
        *_CONTENT_LENGTH_HEADER_VALIDATORS,
    ),
)

_ROUTES = (
    _ADD_TARGET,
    _RECO_COUNTS_REPORT,
    _DELETE_TARGET,
    _DATABASE_SUMMARY,
    _TARGET_LIST,
    _GET_TARGET,
    _GET_DUPLICATES,
    _UPDATE_TARGET,
    _GENERATE_INSTANCE,
    _TARGET_SUMMARY,
)


@beartype
def match_route(*, request_path: str, request_method: str) -> Route:
    """Return the route which a request was made to.

    Args:
        request_path: The path of the request.
        request_method: The HTTP method of the request.

    Returns:
        The one route which the request matches.
    """
    (matching_route,) = (
        route
        for route in _ROUTES
        if re.fullmatch(pattern=route.path_pattern, string=request_path)
        is not None
        and request_method == route.http_method
    )
    return matching_route
