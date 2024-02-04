"""
Validators for target names.
"""

import json
import logging
from http import HTTPStatus

from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._services_validators.exceptions import (
    Fail,
    OopsErrorOccurredResponse,
    TargetNameExist,
)
from mock_vws.database import VuforiaDatabase

_LOGGER = logging.getLogger(__name__)


def validate_name_characters_in_range(
    request_body: bytes,
    request_method: str,
    request_path: str,
) -> None:
    """
    Validate the characters in the name argument given to a VWS endpoint.

    Args:
        request_body: The body of the request.
        request_method: The HTTP method the request is using.
        request_path: The path to the endpoint.

    Raises:
        OopsErrorOccurredResponse: Characters are out of range and the request
            is trying to make a new target.
        TargetNameExist: Characters are out of range and the request is for
            another endpoint.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    if "name" not in json.loads(request_text):
        return

    name = json.loads(request_text)["name"]

    max_character_ord = 65535
    if all(ord(character) <= max_character_ord for character in name):
        return

    if (request_method, request_path) == ("POST", "/targets"):
        _LOGGER.warning(msg="Characters are out of range.")
        raise OopsErrorOccurredResponse

    _LOGGER.warning(msg="Characters are out of range.")
    raise TargetNameExist


def validate_name_type(request_body: bytes) -> None:
    """
    Validate the type of the name argument given to a VWS endpoint.

    Args:
        request_body: The body of the request.

    Raises:
        Fail: A name is given and it is not a string.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    if "name" not in json.loads(request_text):
        return

    name = json.loads(request_text)["name"]

    if isinstance(name, str):
        return

    _LOGGER.warning(msg="Name is not a string.")
    raise Fail(status_code=HTTPStatus.BAD_REQUEST)


def validate_name_length(request_body: bytes) -> None:
    """
    Validate the length of the name argument given to a VWS endpoint.

    Args:
        request_body: The body of the request.

    Raises:
        Fail: A name is given and it is not a between 1 and 64 characters in
            length.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    if "name" not in json.loads(request_text):
        return

    name = json.loads(request_text)["name"]

    max_length = 64
    if name and len(name) <= max_length:
        return

    _LOGGER.warning(msg="Name is not between 1 and 64 characters in length.")
    raise Fail(status_code=HTTPStatus.BAD_REQUEST)


def validate_name_does_not_exist_new_target(
    databases: set[VuforiaDatabase],
    request_body: bytes,
    request_headers: dict[str, str],
    request_method: str,
    request_path: str,
) -> None:
    """
    Validate that the name does not exist for any existing target.

    Args:
        databases: All Vuforia databases.
        request_body: The body of the request.
        request_headers: The headers sent with the request.
        request_method: The HTTP method the request is using.
        request_path: The path to the endpoint.

    Raises:
        TargetNameExist: The target name already exists.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    if "name" not in json.loads(request_text):
        return

    split_path = request_path.split("/")

    split_path_no_target_id_length = 2
    if len(split_path) != split_path_no_target_id_length:
        return

    name = json.loads(request_text)["name"]
    database = get_database_matching_server_keys(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )

    matching_name_targets = [
        target
        for target in database.not_deleted_targets
        if target.name == name
    ]

    if not matching_name_targets:
        return

    _LOGGER.warning(msg="Target name already exists.")
    raise TargetNameExist


def validate_name_does_not_exist_existing_target(
    request_headers: dict[str, str],
    request_body: bytes,
    request_method: str,
    request_path: str,
    databases: set[VuforiaDatabase],
) -> None:
    """
    Validate that the name does not exist for any existing target apart from
    the one being updated.

    Args:
        databases: All Vuforia databases.
        request_body: The body of the request.
        request_headers: The headers sent with the request.
        request_method: The HTTP method the request is using.
        request_path: The path to the endpoint.

    Raises:
        TargetNameExist: The target name is not the same as the name of the
            target being updated but it is the same as another target.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    if "name" not in json.loads(request_text):
        return

    split_path = request_path.split("/")
    split_path_no_target_id_length = 2
    if len(split_path) == split_path_no_target_id_length:
        return

    target_id = split_path[-1]

    name = json.loads(request_text)["name"]
    database = get_database_matching_server_keys(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )

    matching_name_targets = [
        target
        for target in database.not_deleted_targets
        if target.name == name
    ]

    if not matching_name_targets:
        return

    (matching_name_target,) = matching_name_targets
    if matching_name_target.target_id == target_id:
        return

    _LOGGER.warning("Name already exists for another target.")
    raise TargetNameExist
