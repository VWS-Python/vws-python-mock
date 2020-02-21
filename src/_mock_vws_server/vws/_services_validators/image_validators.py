"""
Image validators to use in the mock.
"""

import binascii
import io
import uuid
from typing import Any, Callable, Dict, Tuple

import wrapt
from flask import request
from PIL import Image
from requests import codes
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._base64_decoding import decode_base64
from mock_vws._constants import ResultCodes
from mock_vws._mock_common import json_dump


@wrapt.decorator
def validate_image_format(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the format of the image given to a VWS endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNPROCESSABLE_ENTITY` response if the image is given and is not
        either a PNG or a JPEG.
    """

    if not request.data:
        return wrapped(*args, **kwargs)

    image = request.get_json(force=True).get('image')

    if image is None:
        return wrapped(*args, **kwargs)

    decoded = decode_base64(encoded_data=image)
    image_file = io.BytesIO(decoded)
    pil_image = Image.open(image_file)

    if pil_image.format in ('PNG', 'JPEG'):
        return wrapped(*args, **kwargs)

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.BAD_IMAGE.value,
    }
    return json_dump(body), codes.UNPROCESSABLE_ENTITY


@wrapt.decorator
def validate_image_color_space(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the color space of the image given to a VWS endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNPROCESSABLE_ENTITY` response if the image is given and is not
        in either the RGB or greyscale color space.
    """

    if not request.data:
        return wrapped(*args, **kwargs)

    image = request.get_json(force=True).get('image')

    if image is None:
        return wrapped(*args, **kwargs)

    decoded = decode_base64(encoded_data=image)
    image_file = io.BytesIO(decoded)
    pil_image = Image.open(image_file)

    if pil_image.mode in ('L', 'RGB'):
        return wrapped(*args, **kwargs)

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.BAD_IMAGE.value,
    }
    return json_dump(body), codes.UNPROCESSABLE_ENTITY


@wrapt.decorator
def validate_image_size(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the file size of the image given to a VWS endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNPROCESSABLE_ENTITY` response if the image is given and is not
        under a certain file size threshold.
    """

    if not request.data:
        return wrapped(*args, **kwargs)

    image = request.get_json(force=True).get('image')

    if image is None:
        return wrapped(*args, **kwargs)

    decoded = decode_base64(encoded_data=image)

    if len(decoded) <= 2359293:
        return wrapped(*args, **kwargs)

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.IMAGE_TOO_LARGE.value,
    }
    return json_dump(body), codes.UNPROCESSABLE_ENTITY


@wrapt.decorator
def validate_image_is_image(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate that the given image data is actually an image file.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNPROCESSABLE_ENTITY` response if image data is given and it is not
        an image file.
    """

    if not request.data:
        return wrapped(*args, **kwargs)

    image = request.get_json(force=True).get('image')

    if image is None:
        return wrapped(*args, **kwargs)

    decoded = decode_base64(encoded_data=image)
    image_file = io.BytesIO(decoded)

    try:
        Image.open(image_file)
    except OSError:
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.BAD_IMAGE.value,
        }
        return json_dump(body), codes.UNPROCESSABLE_ENTITY

    return wrapped(*args, **kwargs)


@wrapt.decorator
def validate_image_encoding(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate that the given image data can be base64 decoded.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNPROCESSABLE_ENTITY` response if image data is given and it cannot
        be base64 decoded.
    """

    if not request.data:
        return wrapped(*args, **kwargs)

    if 'image' not in request.get_json(force=True):
        return wrapped(*args, **kwargs)

    image = request.get_json(force=True).get('image')

    try:
        decode_base64(encoded_data=image)
    except binascii.Error:
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.FAIL.value,
        }
        return json_dump(body), codes.UNPROCESSABLE_ENTITY

    return wrapped(*args, **kwargs)


@wrapt.decorator
def validate_image_data_type(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate that the given image data is a string.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `BAD_REQUEST` response if image data is given and it is not a
        string.
    """

    if not request.data:
        return wrapped(*args, **kwargs)

    if 'image' not in request.get_json(force=True):
        return wrapped(*args, **kwargs)

    image = request.get_json(force=True).get('image')

    if isinstance(image, str):
        return wrapped(*args, **kwargs)

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.FAIL.value,
    }
    return json_dump(body), codes.BAD_REQUEST
