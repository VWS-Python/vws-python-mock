"""Image validators to use in the mock."""

import binascii
import io
import json
import logging
from http import HTTPStatus

from beartype import beartype
from PIL import Image

from mock_vws._base64_decoding import decode_base64
from mock_vws._services_validators.exceptions import (
    BadImageError,
    FailError,
    ImageTooLargeError,
)

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_image_integrity(*, request_body: bytes) -> None:
    """Validate the integrity of the image given to a VWS endpoint.

    Args:
        request_body: The body of the request.

    Raises:
        BadImageError: The image is given and is not a valid image file.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    image = json.loads(s=request_text).get("image")
    if image is None:
        return

    decoded = decode_base64(encoded_data=image)

    image_file = io.BytesIO(initial_bytes=decoded)
    pil_image = Image.open(fp=image_file)

    try:
        pil_image.verify()
    except SyntaxError as exc:
        _LOGGER.warning(msg="The image is not a valid image file.")
        raise BadImageError from exc


@beartype
def validate_image_format(*, request_body: bytes) -> None:
    """Validate the format of the image given to a VWS endpoint.

    Args:
        request_body: The body of the request.

    Raises:
        BadImageError:  The image is given and is not either a PNG or a JPEG.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    image = json.loads(s=request_text).get("image")

    if image is None:
        return

    decoded = decode_base64(encoded_data=image)
    image_file = io.BytesIO(initial_bytes=decoded)
    pil_image = Image.open(fp=image_file)

    if pil_image.format in {"PNG", "JPEG"}:
        return

    _LOGGER.warning(msg="The image is not a PNG or JPEG.")
    raise BadImageError


@beartype
def validate_image_color_space(*, request_body: bytes) -> None:
    """Validate the color space of the image given to a VWS endpoint.

    Args:
        request_body: The body of the request.

    Raises:
        BadImageError: The image is given and is not in either the RGB or
            greyscale color space.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    image = json.loads(s=request_text).get("image")

    if image is None:
        return

    decoded = decode_base64(encoded_data=image)
    image_file = io.BytesIO(initial_bytes=decoded)
    pil_image = Image.open(fp=image_file)

    if pil_image.mode in {"L", "RGB"}:
        return

    _LOGGER.warning(
        msg="The image is not in the RGB or greyscale color space.",
    )
    raise BadImageError


@beartype
def validate_image_size(*, request_body: bytes) -> None:
    """Validate the file size of the image given to a VWS endpoint.

    Args:
        request_body: The body of the request.

    Raises:
        ImageTooLargeError:  The image is given and is not under a certain file
            size threshold.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    image = json.loads(s=request_text).get("image")

    if image is None:
        return

    decoded = decode_base64(encoded_data=image)

    max_allowed_size = 2_359_293
    if len(decoded) <= max_allowed_size:
        return

    _LOGGER.warning(msg="The image is too large.")
    raise ImageTooLargeError


@beartype
def validate_image_is_image(*, request_body: bytes) -> None:
    """Validate that the given image data is actually an image file.

    Args:
        request_body: The body of the request.

    Raises:
        BadImageError: Image data is given and it is not an image file.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    image = json.loads(s=request_text).get("image")

    if image is None:
        return

    decoded = decode_base64(encoded_data=image)
    image_file = io.BytesIO(initial_bytes=decoded)

    try:
        Image.open(fp=image_file)
    except OSError as exc:
        raise BadImageError from exc


@beartype
def validate_image_encoding(*, request_body: bytes) -> None:
    """Validate that the given image data can be base64 decoded.

    Args:
        request_body: The body of the request.

    Raises:
        FailError: Image data is given and it cannot be base64 decoded.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    if "image" not in json.loads(s=request_text):
        return

    image = json.loads(s=request_text).get("image")

    try:
        decode_base64(encoded_data=image)
    except binascii.Error as exc:
        _LOGGER.warning('Image data cannot be base64 decoded: "%s"', exc)
        raise FailError(status_code=HTTPStatus.UNPROCESSABLE_ENTITY) from exc


@beartype
def validate_image_data_type(*, request_body: bytes) -> None:
    """Validate that the given image data is a string.

    Args:
        request_body: The body of the request.

    Raises:
        FailError: Image data is given and it is not a string.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    if "image" not in json.loads(s=request_text):
        return

    image = json.loads(s=request_text).get("image")

    if isinstance(image, str):
        return

    _LOGGER.warning('Image data is not a string: "%s"', image)
    raise FailError(status_code=HTTPStatus.BAD_REQUEST)
