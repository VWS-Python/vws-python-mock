"""
Validators for JSON keys.
"""

import json
import logging
import re
from dataclasses import dataclass
from http import HTTPStatus

from requests_mock import DELETE, GET, POST, PUT

from .exceptions import Fail

_LOGGER = logging.getLogger(__name__)


@dataclass
class _Route:
    """
    A representation of a VWS route.

    Args:
        path_pattern: The end part of a URL pattern. E.g. `/targets` or
            `/targets/.+`.
        http_methods: HTTP methods that map to the route function.
        mandatory_keys: Keys required by the endpoint.
        optional_keys: Keys which are not required by the endpoint but which
            are allowed.
    """

    path_pattern: str
    http_methods: set[str]
    mandatory_keys: set[str]
    optional_keys: set[str]


def validate_keys(
    request_body: bytes,
    request_path: str,
    request_method: str,
) -> None:
    """
    Validate the request keys given to a VWS endpoint.

    Args:
        request_body: The body of the request.
        request_path: The path of the request.
        request_method: The HTTP method of the request.

    Raises:
        Fail: Any given keys are not allowed, or if any required keys are
            missing.
    """
    target_id_pattern = "[A-Za-z0-9]+"
    add_target = _Route(
        path_pattern="/targets",
        http_methods={POST},
        mandatory_keys={"image", "width", "name"},
        optional_keys={"active_flag", "application_metadata"},
    )

    delete_target = _Route(
        path_pattern=f"/targets/{target_id_pattern}",
        http_methods={DELETE},
        mandatory_keys=set(),
        optional_keys=set(),
    )

    database_summary = _Route(
        path_pattern="/summary",
        http_methods={GET},
        mandatory_keys=set(),
        optional_keys=set(),
    )

    target_list = _Route(
        path_pattern="/targets",
        http_methods={GET},
        mandatory_keys=set(),
        optional_keys=set(),
    )

    get_target = _Route(
        path_pattern=f"/targets/{target_id_pattern}",
        http_methods={GET},
        mandatory_keys=set(),
        optional_keys=set(),
    )

    target_summary = _Route(
        path_pattern=f"/summary/{target_id_pattern}",
        http_methods={GET},
        mandatory_keys=set(),
        optional_keys=set(),
    )

    get_duplicates = _Route(
        path_pattern=f"/duplicates/{target_id_pattern}",
        http_methods={GET},
        mandatory_keys=set(),
        optional_keys=set(),
    )

    update_target = _Route(
        path_pattern=f"/targets/{target_id_pattern}",
        http_methods={PUT},
        mandatory_keys=set(),
        optional_keys={
            "active_flag",
            "application_metadata",
            "image",
            "name",
            "width",
        },
    )

    target_summary = _Route(
        path_pattern=f"/summary/{target_id_pattern}",
        http_methods={GET},
        mandatory_keys=set(),
        optional_keys=set(),
    )

    routes = (
        add_target,
        delete_target,
        database_summary,
        target_list,
        get_target,
        get_duplicates,
        update_target,
        target_summary,
    )

    (matching_route,) = (
        route
        for route in routes
        if re.match(re.compile(f"{route.path_pattern}$"), request_path)
        and request_method in route.http_methods
    )

    mandatory_keys = matching_route.mandatory_keys
    optional_keys = matching_route.optional_keys
    allowed_keys = mandatory_keys.union(optional_keys)

    if not request_body and not allowed_keys:
        return

    request_text = request_body.decode()
    request_json = json.loads(request_text)
    given_keys = set(request_json.keys())
    all_given_keys_allowed = given_keys.issubset(allowed_keys)
    all_mandatory_keys_given = mandatory_keys.issubset(given_keys)

    if all_given_keys_allowed and all_mandatory_keys_given:
        return

    _LOGGER.warning(msg="Invalid keys given to endpoint.")
    raise Fail(status_code=HTTPStatus.BAD_REQUEST)
