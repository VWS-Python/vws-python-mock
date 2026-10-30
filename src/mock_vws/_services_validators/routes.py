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
from .instance_id_validators import (
    validate_instance_id_not_empty,
    validate_instance_id_type,
)
from .json_validators import (
    validate_vumark_instance_json,
)
from .key_validators import validate_keys
from .project_state_validators import validate_project_state
from .target_validators import validate_target_id_exists

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
        validators: The validators which apply to the route, in the order in
            which they apply.

    Attributes:
        path_pattern: A pattern which matches the path of the route, and only
            the path of the route.
        http_method: The HTTP method of the route.
        mandatory_keys: Keys required in the request body.
        optional_keys: Keys which are not required in the request body but
            which are allowed.
        validators: The validators which apply to the route, in the order in
            which they apply.
    """

    path_pattern: str
    http_method: HTTPMethod
    mandatory_keys: frozenset[str]
    optional_keys: frozenset[str]
    validators: Sequence[Validator]


# Every route is quota checked and refused when the project is in a state
# which does not allow it. The request rate limits are applied before any
# route validator, by ``run_services_validators``.

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


_GENERATE_INSTANCE = Route(
    path_pattern=f"/targets/{_TARGET_ID_PATTERN}/instances",
    http_method=HTTPMethod.POST,
    mandatory_keys=frozenset({"instance_id"}),
    optional_keys=frozenset(),
    validators=(
        validate_project_state,
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


_ROUTES = (_GENERATE_INSTANCE,)


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
