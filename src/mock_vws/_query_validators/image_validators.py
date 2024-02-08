"""
Input validators for the image field use in the mock query API.
"""

import io
import logging
from email.message import EmailMessage

from PIL import Image

from mock_vws._query_tools import TypedMultiPartParser
from mock_vws._query_validators.exceptions import (
    BadImage,
    ImageNotGiven,
    RequestEntityTooLarge,
)

_LOGGER = logging.getLogger(__name__)


def validate_image_field_given(
    request_headers: dict[str, str],
    request_body: bytes,
) -> None:
    """
    Validate that the image field is given.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        ImageNotGiven: The image field is not given.
    """
    email_message = EmailMessage()
    email_message["Content-Type"] = request_headers["Content-Type"]
    boundary = email_message.get_boundary()
    assert isinstance(boundary, str)
    parser = TypedMultiPartParser()
    _, files = parser.parse(
        stream=io.BytesIO(request_body),
        boundary=boundary.encode("utf-8"),
        content_length=len(request_body),
    )
    if files.get("image") is not None:
        return

    _LOGGER.warning(msg="The image field is not given.")
    raise ImageNotGiven


def validate_image_file_size(
    request_headers: dict[str, str],
    request_body: bytes,
) -> None:
    """
    Validate the file size of the image given to the query endpoint.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        RequestEntityTooLarge: The image file size is too large.
    """
    email_message = EmailMessage()
    email_message["Content-Type"] = request_headers["Content-Type"]
    boundary = email_message.get_boundary()
    assert isinstance(boundary, str)
    parser = TypedMultiPartParser()
    _, files = parser.parse(
        stream=io.BytesIO(request_body),
        boundary=boundary.encode("utf-8"),
        content_length=len(request_body),
    )
    image_part = files["image"]
    image_value = image_part.stream.read()

    # This is the documented maximum size of a PNG as per.
    # https://library.vuforia.com/web-api/vuforia-query-web-api.
    # However, the tests show that this maximum size also applies to JPEG
    # files.
    max_bytes = 2 * 1024 * 1024
    # Ignore coverage on this as there is a bug in urllib3 which means that we
    # do not trigger this exception.
    # See https://github.com/urllib3/urllib3/issues/2733.
    if len(image_value) > max_bytes:  # pragma: no cover
        _LOGGER.warning(msg="The image file size is too large.")
        raise RequestEntityTooLarge


def validate_image_dimensions(
    request_headers: dict[str, str],
    request_body: bytes,
) -> None:
    """
    Validate the dimensions the image given to the query endpoint.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        BadImage: The image is given and is not within the maximum width and
            height limits.
    """
    email_message = EmailMessage()
    email_message["Content-Type"] = request_headers["Content-Type"]
    boundary = email_message.get_boundary()
    assert isinstance(boundary, str)
    parser = TypedMultiPartParser()
    _, files = parser.parse(
        stream=io.BytesIO(request_body),
        boundary=boundary.encode("utf-8"),
        content_length=len(request_body),
    )
    image_part = files["image"]
    image_value = image_part.stream.read()
    image_file = io.BytesIO(image_value)
    pil_image = Image.open(image_file)
    max_width = 30000
    max_height = 30000
    if pil_image.height <= max_height and pil_image.width <= max_width:
        return

    _LOGGER.warning(msg="The image dimensions are too large.")
    raise BadImage


def validate_image_format(
    request_headers: dict[str, str],
    request_body: bytes,
) -> None:
    """
    Validate the format of the image given to the query endpoint.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        BadImage: The image is given and is not either a PNG or a JPEG.
    """
    email_message = EmailMessage()
    email_message["Content-Type"] = request_headers["Content-Type"]
    boundary = email_message.get_boundary()
    assert isinstance(boundary, str)
    parser = TypedMultiPartParser()
    _, files = parser.parse(
        stream=io.BytesIO(request_body),
        boundary=boundary.encode("utf-8"),
        content_length=len(request_body),
    )
    image_part = files["image"]
    pil_image = Image.open(image_part.stream)

    if pil_image.format in {"PNG", "JPEG"}:
        return

    _LOGGER.warning(msg="The image format is not PNG or JPEG.")
    raise BadImage


def validate_image_is_image(
    request_headers: dict[str, str],
    request_body: bytes,
) -> None:
    """
    Validate that the given image data is actually an image file.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        BadImage: Image data is given and it is not an image file.
    """
    email_message = EmailMessage()
    email_message["Content-Type"] = request_headers["Content-Type"]
    boundary = email_message.get_boundary()
    assert isinstance(boundary, str)
    parser = TypedMultiPartParser()
    _, files = parser.parse(
        stream=io.BytesIO(request_body),
        boundary=boundary.encode("utf-8"),
        content_length=len(request_body),
    )
    image_part = files["image"]
    image_file = image_part.stream

    try:
        Image.open(image_file)
    except OSError as exc:
        _LOGGER.warning(msg="The image is not an image file.")
        raise BadImage from exc
