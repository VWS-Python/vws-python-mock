"""
Image validators to use in the mock.
"""

import binascii
import io
import json
from typing import Dict, List

from PIL import Image
from requests import codes

from mock_vws._base64_decoding import decode_base64
from mock_vws._services_validators.exceptions import (
    BadImage,
    Fail,
    ImageTooLarge,
)
from mock_vws.database import VuforiaDatabase


def validate_image_format(
    request_text: str,
) -> None:
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
    if not request_text:
        return

    image = json.loads(request_text).get('image')

    if image is None:
        return

    decoded = decode_base64(encoded_data=image)
    image_file = io.BytesIO(decoded)
    pil_image = Image.open(image_file)

    if pil_image.format in ('PNG', 'JPEG'):
        return

    raise BadImage


def validate_image_color_space(
    request_text: str,
) -> None:
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

    if not request_text:
        return

    image = json.loads(request_text).get('image')

    if image is None:
        return

    decoded = decode_base64(encoded_data=image)
    image_file = io.BytesIO(decoded)
    pil_image = Image.open(image_file)

    if pil_image.mode in ('L', 'RGB'):
        return

    raise BadImage


def validate_image_size(
    request_text: str,
) -> None:
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

    if not request_text:
        return

    image = json.loads(request_text).get('image')

    if image is None:
        return

    decoded = decode_base64(encoded_data=image)

    if len(decoded) <= 2359293:
        return

    raise ImageTooLarge


def validate_image_is_image(
    request_text: str,
) -> None:
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

    if not request_text:
        return

    image = json.loads(request_text).get('image')

    if image is None:
        return

    decoded = decode_base64(encoded_data=image)
    image_file = io.BytesIO(decoded)

    try:
        Image.open(image_file)
    except OSError:
        raise BadImage


def validate_image_encoding(
    request_text: str,
) -> None:
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

    if not request_text:
        return

    if 'image' not in json.loads(request_text):
        return

    image = json.loads(request_text).get('image')

    try:
        decode_base64(encoded_data=image)
    except binascii.Error:
        raise Fail(status_code=codes.UNPROCESSABLE_ENTITY)


def validate_image_data_type(
    request_text: str,
) -> None:
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

    if not request_text:
        return

    if 'image' not in json.loads(request_text):
        return

    image = json.loads(request_text).get('image')

    if isinstance(image, str):
        return

    raise Fail(status_code=codes.BAD_REQUEST)
