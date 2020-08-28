"""
Image validators to use in the mock.
"""

import binascii
import io
import json
from http import HTTPStatus

from PIL import Image

from mock_vws._base64_decoding import decode_base64
from mock_vws._services_validators.exceptions import (
    BadImage,
    Fail,
    ImageTooLarge,
)


def validate_image_format(request_body: bytes) -> None:
    """
    Validate the format of the image given to a VWS endpoint.

    Args:
        request_body: The body of the request.

    Raises:
        BadImage:  The image is given and is not either a PNG or a JPEG.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    image = json.loads(request_text).get('image')

    if image is None:
        return

    decoded = decode_base64(encoded_data=image)
    image_file = io.BytesIO(decoded)
    pil_image = Image.open(image_file)

    if pil_image.format in ('PNG', 'JPEG'):
        return

    raise BadImage


def validate_image_color_space(request_body: bytes) -> None:
    """
    Validate the color space of the image given to a VWS endpoint.

    Args:
        request_body: The body of the request.

    Raises:
        BadImage: The image is given and is not in either the RGB or
            greyscale color space.
    """

    if not request_body:
        return

    request_text = request_body.decode()
    image = json.loads(request_text).get('image')

    if image is None:
        return

    decoded = decode_base64(encoded_data=image)
    image_file = io.BytesIO(decoded)
    pil_image = Image.open(image_file)

    if pil_image.mode in ('L', 'RGB'):
        return

    raise BadImage


def validate_image_size(request_body: bytes) -> None:
    """
    Validate the file size of the image given to a VWS endpoint.

    Args:
        request_body: The body of the request.

    Raises:
        ImageTooLarge:  The image is given and is not under a certain file
            size threshold.
    """

    if not request_body:
        return

    request_text = request_body.decode()
    image = json.loads(request_text).get('image')

    if image is None:
        return

    decoded = decode_base64(encoded_data=image)

    if len(decoded) <= 2359293:
        return

    raise ImageTooLarge


def validate_image_is_image(request_body: bytes) -> None:
    """
    Validate that the given image data is actually an image file.

    Args:
        request_body: The body of the request.

    Raises:
        BadImage: Image data is given and it is not an image file.
    """

    if not request_body:
        return

    request_text = request_body.decode()
    image = json.loads(request_text).get('image')

    if image is None:
        return

    decoded = decode_base64(encoded_data=image)
    image_file = io.BytesIO(decoded)

    try:
        Image.open(image_file)
    except OSError as exc:
        raise BadImage from exc


def validate_image_encoding(request_body: bytes) -> None:
    """
    Validate that the given image data can be base64 decoded.

    Args:
        request_body: The body of the request.

    Raises:
        Fail: Image data is given and it cannot be base64 decoded.
    """

    if not request_body:
        return

    request_text = request_body.decode()
    if 'image' not in json.loads(request_text):
        return

    image = json.loads(request_text).get('image')

    try:
        decode_base64(encoded_data=image)
    except binascii.Error as exc:
        raise Fail(status_code=HTTPStatus.UNPROCESSABLE_ENTITY) from exc


def validate_image_data_type(request_body: bytes) -> None:
    """
    Validate that the given image data is a string.

    Args:
        request_body: The body of the request.

    Raises:
        Fail: Image data is given and it is not a string.
    """

    if not request_body:
        return

    request_text = request_body.decode()
    if 'image' not in json.loads(request_text):
        return

    image = json.loads(request_text).get('image')

    if isinstance(image, str):
        return

    raise Fail(status_code=HTTPStatus.BAD_REQUEST)
