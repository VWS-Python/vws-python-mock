"""Input validators for the image field use in the mock query API."""

import io
import logging
from collections.abc import Mapping
from email.message import EmailMessage

from beartype import beartype
from PIL import Image
from werkzeug.datastructures import FileStorage, MultiDict
from werkzeug.formparser import MultiPartParser

from mock_vws._query_validators.exceptions import (
    BadImageError,
    ImageNotGivenError,
    RequestEntityTooLargeError,
)

_LOGGER = logging.getLogger(name=__name__)


def _parse_multipart_files(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
) -> MultiDict[str, FileStorage]:
    """Parse the multipart body and return the files section.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Returns:
        The files parsed from the multipart body.
    """
    email_message = EmailMessage()
    email_message["Content-Type"] = request_headers["Content-Type"]
    boundary = email_message.get_boundary(failobj="")
    parser = MultiPartParser()
    _, files = parser.parse(
        stream=io.BytesIO(initial_bytes=request_body),
        boundary=boundary.encode(encoding="utf-8"),
        content_length=len(request_body),
    )
    return files


@beartype
def _parse_multipart_files(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
) -> MultiDict[str, FileStorage]:
    """Parse the multipart body and return the files section.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Returns:
        The files parsed from the multipart body.
    """
    email_message = EmailMessage()
    email_message["Content-Type"] = request_headers["Content-Type"]
    boundary = email_message.get_boundary(failobj="")
    parser = MultiPartParser()
    _, files = parser.parse(
        stream=io.BytesIO(initial_bytes=request_body),
        boundary=boundary.encode(encoding="utf-8"),
        content_length=len(request_body),
    )
    return files


@beartype
def validate_image_field_given(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
) -> None:
    """Validate that the image field is given.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        ImageNotGivenError: The image field is not given.
    """
    files = _parse_multipart_files(
        request_headers=request_headers,
        request_body=request_body,
    )
    if files.get(key="image") is not None:
        return

    _LOGGER.warning(msg="The image field is not given.")
    raise ImageNotGivenError


@beartype
def validate_image_file_size(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
) -> None:
    """Validate the file size of the image given to the query endpoint.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        RequestEntityTooLargeError: The image file size is too large.
    """
    files = _parse_multipart_files(
        request_headers=request_headers,
        request_body=request_body,
    )
    image_part = files["image"]
    image_value = image_part.stream.read()

    # This is the documented maximum size of a PNG as per.
    # https://developer.vuforia.com/library/web-api/vuforia-query-web-api.
    # However, the tests show that this maximum size also applies to JPEG
    # files.
    max_bytes = 2 * 1024 * 1024
    # Ignore coverage on this as there is a bug in urllib3 which means that we
    # do not trigger this exception.
    # See https://github.com/urllib3/urllib3/issues/2733.
    if len(image_value) > max_bytes:  # pragma: no cover
        _LOGGER.warning(msg="The image file size is too large.")
        raise RequestEntityTooLargeError


@beartype
def validate_image_dimensions(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
) -> None:
    """Validate the dimensions the image given to the query endpoint.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        BadImageError: The image is given and is not within the maximum width
            and height limits.
    """
    files = _parse_multipart_files(
        request_headers=request_headers,
        request_body=request_body,
    )
    image_part = files["image"]
    image_value = image_part.stream.read()
    image_file = io.BytesIO(initial_bytes=image_value)
    pil_image = Image.open(fp=image_file)
    max_width = 30000
    max_height = 30000
    if pil_image.height <= max_height and pil_image.width <= max_width:
        return

    _LOGGER.warning(msg="The image dimensions are too large.")
    raise BadImageError


@beartype
def validate_image_format(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
) -> None:
    """Validate the format of the image given to the query endpoint.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        BadImageError: The image is given and is not either a PNG or a JPEG.
    """
    files = _parse_multipart_files(
        request_headers=request_headers,
        request_body=request_body,
    )
    image_part = files["image"]
    pil_image = Image.open(fp=image_part.stream)

    if pil_image.format in {"PNG", "JPEG"}:
        return

    _LOGGER.warning(msg="The image format is not PNG or JPEG.")
    raise BadImageError


@beartype
def validate_image_is_image(
    request_headers: Mapping[str, str],
    request_body: bytes,
) -> None:
    """Validate that the given image data is actually an image file.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        BadImageError: Image data is given and it is not an image file.
    """
    files = _parse_multipart_files(
        request_headers=request_headers,
        request_body=request_body,
    )
    image_file = files["image"].stream

    try:
        Image.open(fp=image_file)
    except OSError as exc:
        _LOGGER.warning(msg="The image is not an image file.")
        raise BadImageError from exc
