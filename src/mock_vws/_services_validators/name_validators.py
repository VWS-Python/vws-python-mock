"""
Validators for target names.
"""

import json
from typing import Dict, List

from requests import codes

from mock_vws._services_validators.exceptions import (
    Fail,
    OopsErrorOccurredResponse,
    TargetNameExist,
)
from mock_vws.database import VuforiaDatabase


def validate_name_characters_in_range(
    request_text: str,
) -> None:
    """
    Validate the characters in the name argument given to a VWS endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A ``FORBIDDEN`` response if the name is given includes characters
        outside of the accepted range.
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


def validate_name_type(
    request_text: str,
) -> None:
    """
    Validate the type of the name argument given to a VWS endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the name is given and not a string.
        is not between 1 and
        64 characters in length.
    """

    if not request_text:
        return

    if 'name' not in json.loads(request_text):
        return

    name = json.loads(request_text)['name']

    if isinstance(name, str):
        return

    raise Fail(status_code=codes.BAD_REQUEST)


def validate_name_length(
    request_text: str,
) -> None:
    """
    Validate the length of the name argument given to a VWS endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the name is given is not between 1 and 64
        characters in length.
    """
    if not request_text:
        return

    if 'name' not in json.loads(request_text):
        return

    name = json.loads(request_text)['name']

    if name and len(name) < 65:
        return

    raise Fail(status_code=codes.BAD_REQUEST)
