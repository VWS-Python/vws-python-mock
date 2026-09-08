"""Input validators for the image field use in the mock query API."""

import io
import logging

from beartype import beartype

from mock_vws._image_opening import open_image
from mock_vws._query_validators.exceptions import (
    BadImageError,
    ImageNotGivenError,
    RequestEntityTooLargeError,
)
from mock_vws._query_validators.multipart import MultipartForm

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_image_field_given(*, form: MultipartForm) -> None:
    """Validate that the image field is given.

    Args:
        form: The parsed body of the request.

    Raises:
        ImageNotGivenError: The image field is not given.
    """
    if "image" in form.files:
        return

    _LOGGER.warning(msg="The image field is not given.")
    raise ImageNotGivenError


@beartype
def validate_image_file_size(*, form: MultipartForm) -> None:
    """Validate the file size of the image given to the query endpoint.

    Args:
        form: The parsed body of the request.

    Raises:
        RequestEntityTooLargeError: The image file size is too large.
    """
    image_value = form.files["image"]

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
def validate_image_dimensions(*, form: MultipartForm) -> None:
    """Validate the dimensions the image given to the query endpoint.

    Args:
        form: The parsed body of the request.

    Raises:
        BadImageError: The image is given and is not within the maximum width
            and height limits.
    """
    image_file = io.BytesIO(initial_bytes=form.files["image"])
    with open_image(fp=image_file) as pil_image:
        max_width = 30000
        max_height = 30000
        if pil_image.height <= max_height and pil_image.width <= max_width:
            return

    _LOGGER.warning(msg="The image dimensions are too large.")
    raise BadImageError


@beartype
def validate_image_format(*, form: MultipartForm) -> None:
    """Validate the format of the image given to the query endpoint.

    Args:
        form: The parsed body of the request.

    Raises:
        BadImageError: The image is given and is not either a PNG or a JPEG.
    """
    image_file = io.BytesIO(initial_bytes=form.files["image"])
    with open_image(fp=image_file) as pil_image:
        if pil_image.format in {"PNG", "JPEG"}:
            return

    _LOGGER.warning(msg="The image format is not PNG or JPEG.")
    raise BadImageError


@beartype
def validate_image_is_image(*, form: MultipartForm) -> None:
    """Validate that the given image data is actually an image file.

    Args:
        form: The parsed body of the request.

    Raises:
        BadImageError: Image data is given and it is not an image file.
    """
    image_file = io.BytesIO(initial_bytes=form.files["image"])

    try:
        with open_image(fp=image_file) as _:
            pass
    except OSError as exc:
        _LOGGER.warning(msg="The image is not an image file.")
        raise BadImageError from exc
