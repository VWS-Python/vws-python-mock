"""
Input validators to use in the mock.
"""

import binascii
import numbers
import uuid
from json.decoder import JSONDecodeError
from pathlib import Path
from typing import Any, Callable, Dict, Set, Tuple

import wrapt
from flask import make_response, request
from requests import codes
from requests_mock import POST, PUT
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._base64_decoding import decode_base64
from mock_vws._constants import ResultCodes
from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._mock_common import json_dump
from mock_vws.database import VuforiaDatabase
from mock_vws.states import States


@wrapt.decorator
def validate_active_flag(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the active flag data given to the endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response with a FAIL result code if there is
        active flag data given to the endpoint which is not either a Boolean or
        NULL.
    """
    if not request.data:
        return wrapped(*args, **kwargs)

    if 'active_flag' not in request.get_json(force=True):
        return wrapped(*args, **kwargs)

    active_flag = request.get_json(force=True).get('active_flag')

    if active_flag is None or isinstance(active_flag, bool):
        return wrapped(*args, **kwargs)

    body: Dict[str, str] = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.FAIL.value,
    }
    return json_dump(body), codes.BAD_REQUEST


@wrapt.decorator
def validate_project_state(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the state of the project.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `FORBIDDEN` response with a PROJECT_INACTIVE result code if the
        project is inactive.
    """
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.body,
        request_method=request.method,
        request_path=request.path,
        databases=instance.databases,
    )

    assert isinstance(database, VuforiaDatabase)
    if database.state != States.PROJECT_INACTIVE:
        return wrapped(*args, **kwargs)

    if request.method == 'GET' and 'duplicates' not in request.path:
        return wrapped(*args, **kwargs)

    body: Dict[str, str] = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.PROJECT_INACTIVE.value,
    }
    return json_dump(body), codes.FORBIDDEN


@wrapt.decorator
def validate_not_invalid_json(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate that there is either no JSON given or the JSON given is valid.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response with a FAIL result code if there is invalid
        JSON given to a POST or PUT request.
        A `BAD_REQUEST` with empty text if there is data given to another
        request type.
    """
    if not request.data:
        return wrapped(*args, **kwargs)

    if request.method not in (POST, PUT):
        # TODO this is commented out but not but should maybe be moved to an
        # after_request decorator
        # context.headers.pop('Content-Type')
        return '', codes.OK

    try:
        request.get_json(force=True)
    except JSONDecodeError:
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.FAIL.value,
        }
        return json_dump(body), codes.BAD_REQUEST

    return wrapped(*args, **kwargs)


@wrapt.decorator
def validate_width(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the width argument given to a VWS endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the width is given and is not a positive
        number.
    """

    if not request.data:
        return wrapped(*args, **kwargs)

    if 'width' not in request.get_json(force=True):
        return wrapped(*args, **kwargs)

    width = request.get_json(force=True).get('width')

    width_is_number = isinstance(width, numbers.Number)
    width_positive = width_is_number and width > 0

    if not width_positive:
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.FAIL.value,
        }
        return json_dump(body), codes.BAD_REQUEST

    return wrapped(*args, **kwargs)


@wrapt.decorator
def validate_name_type(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
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

    if not request.data:
        return wrapped(*args, **kwargs)

    if 'name' not in request.get_json(force=True):
        return wrapped(*args, **kwargs)

    name = request.get_json(force=True)['name']

    if isinstance(name, str):
        return wrapped(*args, **kwargs)

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.FAIL.value,
    }
    return json_dump(body), codes.BAD_REQUEST


@wrapt.decorator
def validate_name_length(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
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

    if not request.data:
        return wrapped(*args, **kwargs)

    if 'name' not in request.get_json(force=True):
        return wrapped(*args, **kwargs)

    name = request.get_json(force=True)['name']

    if name and len(str(name)) < 65:
        return wrapped(*args, **kwargs)

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.FAIL.value,
    }
    return json_dump(body), codes.BAD_REQUEST


@wrapt.decorator
def validate_name_characters_in_range(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
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

    if not request.data:
        return wrapped(*args, **kwargs)

    if 'name' not in request.get_json(force=True):
        return wrapped(*args, **kwargs)

    name = request.get_json(force=True)['name']

    if all(ord(character) <= 65535 for character in str(name)):
        return wrapped(*args, **kwargs)

    if (request.method, request.path) == ('POST', '/targets'):
        resources_dir = Path(__file__).parent.parent / 'resources'
        filename = 'oops_error_occurred_response.html'
        oops_resp_file = resources_dir / filename
        text = oops_resp_file.read_text()
        oops_response = make_response(text)
        oops_response.headers['Content-Type'] = 'text/html; charset=UTF-8'
        return oops_response, codes.INTERNAL_SERVER_ERROR

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.TARGET_NAME_EXIST.value,
    }
    return json_dump(body), codes.FORBIDDEN


def validate_keys(
    mandatory_keys: Set[str],
    optional_keys: Set[str],
) -> Callable:
    """
    Args:
        mandatory_keys: Keys required by the endpoint.
        optional_keys: Keys which are not required by the endpoint but which
            are allowed.

    Returns:
        A wrapper function to validate that the keys given to the endpoint are
            all allowed and that the mandatory keys are given.
    """

    # Args here to work around https://github.com/PyCQA/pydocstyle/issues/370.
    #
    # Args:
    #     wrapped: An endpoint function for `requests_mock`.
    #     instance: The class that the endpoint function is in.
    #     args: The arguments given to the endpoint function.
    #     kwargs: The keyword arguments given to the endpoint function.
    @wrapt.decorator
    def wrapper(
        wrapped: Callable[..., Tuple[str, int]],
        instance: Any,  # pylint: disable=unused-argument
        args: Tuple[_RequestObjectProxy, _Context],
        kwargs: Dict,
    ) -> Tuple[str, int]:
        """
        Validate the request keys given to a VWS endpoint.

        Returns:
            The result of calling the endpoint.
            A `BAD_REQUEST` error if any keys are not allowed, or if any
            required keys are missing.
        """

        allowed_keys = mandatory_keys.union(optional_keys)

        if request.text is None and not allowed_keys:
            return wrapped(*args, **kwargs)

        given_keys = set(request.get_json(force=True).keys())
        all_given_keys_allowed = given_keys.issubset(allowed_keys)
        all_mandatory_keys_given = mandatory_keys.issubset(given_keys)

        if all_given_keys_allowed and all_mandatory_keys_given:
            return wrapped(*args, **kwargs)

        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.FAIL.value,
        }
        return json_dump(body), codes.BAD_REQUEST

    wrapper_func: Callable[..., Any] = wrapper
    return wrapper_func


@wrapt.decorator
def validate_metadata_encoding(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate that the given application metadata can be base64 decoded.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNPROCESSABLE_ENTITY` response if application metadata is given and
        it cannot be base64 decoded.
    """

    if not request.data:
        return wrapped(*args, **kwargs)

    if 'application_metadata' not in request.get_json(force=True):
        return wrapped(*args, **kwargs)

    application_metadata = request.get_json(force=True
                                            ).get('application_metadata')

    if application_metadata is None:
        return wrapped(*args, **kwargs)

    try:
        decode_base64(encoded_data=application_metadata)
    except binascii.Error:
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.FAIL.value,
        }
        return json_dump(body), codes.UNPROCESSABLE_ENTITY

    return wrapped(*args, **kwargs)


@wrapt.decorator
def validate_metadata_type(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate that the given application metadata is a string or NULL.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `BAD_REQUEST` response if application metadata is given and it is
        not a string or NULL.
    """

    if not request.data:
        return wrapped(*args, **kwargs)

    if 'application_metadata' not in request.get_json(force=True):
        return wrapped(*args, **kwargs)

    application_metadata = request.get_json(force=True
                                            ).get('application_metadata')

    if application_metadata is None or isinstance(application_metadata, str):
        return wrapped(*args, **kwargs)

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.FAIL.value,
    }
    return json_dump(body), codes.BAD_REQUEST


@wrapt.decorator
def validate_metadata_size(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate that the given application metadata is a string or 1024 * 1024
    bytes or fewer.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNPROCESSABLE_ENTITY` response if application metadata is given and
        it is too large.
    """
    if not request.data:
        return wrapped(*args, **kwargs)

    application_metadata = request.get_json(force=True
                                            ).get('application_metadata')
    if application_metadata is None:
        return wrapped(*args, **kwargs)
    decoded = decode_base64(encoded_data=application_metadata)

    max_metadata_bytes = 1024 * 1024 - 1
    if len(decoded) <= max_metadata_bytes:
        return wrapped(*args, **kwargs)

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.METADATA_TOO_LARGE.value,
    }
    return json_dump(body), codes.UNPROCESSABLE_ENTITY
