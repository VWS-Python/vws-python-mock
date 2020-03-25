"""
Validators for target names.
"""

import json

from requests import codes

from mock_vws._services_validators.exceptions import (
    Fail,
    OopsErrorOccurredResponse,
    TargetNameExist,
)


def validate_name_characters_in_range(
    request_text: str,
    request_method: str,
    request_path: str,
) -> None:
    """
    Validate the characters in the name argument given to a VWS endpoint.

    Args:
        request_text: The content of the request.
        request_method: The HTTP method the request is using.
        request_path: The path to the endpoint.

    Raises:
        OopsErrorOccurredResponse: Characters are out of range and the request
            is trying to make a new target.
        TargetNameExist: Characters are out of range and the request is for
            another endpoint.
    """

    if not request_text:
        return

    if 'name' not in json.loads(request_text):
        return

    name = json.loads(request_text)['name']

    if all(ord(character) <= 65535 for character in name):
        return

    if (request_method, request_path) == ('POST', '/targets'):
        raise OopsErrorOccurredResponse

    raise TargetNameExist


def validate_name_type(request_text: str, ) -> None:
    """
    Validate the type of the name argument given to a VWS endpoint.

    Args:
        request_text: The content of the request.

    Raises:
        Fail: A name is given and it is not a string.
    """

    if not request_text:
        return

    if 'name' not in json.loads(request_text):
        return

    name = json.loads(request_text)['name']

    if isinstance(name, str):
        return

    raise Fail(status_code=codes.BAD_REQUEST)


def validate_name_length(request_text: str, ) -> None:
    """
    Validate the length of the name argument given to a VWS endpoint.

    Args:
        request_text: The content of the request.

    Raises:
        Fail: A name is given and it is not a between 1 and 64 characters in
            length.
    """
    if not request_text:
        return

    if 'name' not in json.loads(request_text):
        return

    name = json.loads(request_text)['name']

    if name and len(name) < 65:
        return

    raise Fail(status_code=codes.BAD_REQUEST)
