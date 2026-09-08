"""Image validators to use in the mock."""

import binascii
import io
import logging
from http import HTTPStatus

from beartype import beartype

from mock_vws._image_opening import open_image
from mock_vws._services_validators.context import ValidatorContext
from mock_vws._services_validators.exceptions import (
    BadImageError,
    FailError,
    ImageTooLargeError,
)

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_image_data_type(*, context: ValidatorContext) -> None:
    """Validate that the given image data is a string.

    Args:
        context: The context of the request.

    Raises:
        FailError: Image data is given and it is not a string.
    """
    request_json = context.request_json
    if "image" not in request_json:
        return

    image = request_json["image"]  # pyrefly: ignore [unknown-variable-type]

    if isinstance(image, str):
        return

    _LOGGER.warning('Image data is not a string: "%s"', image)  # pyrefly: ignore [unknown-argument-type]
    raise FailError(status_code=HTTPStatus.BAD_REQUEST)


@beartype
def validate_image_encoding(*, context: ValidatorContext) -> None:
    """Validate that the given image data can be base64 decoded.

    Args:
        context: The context of the request.

    Raises:
        FailError: Image data is given and it cannot be base64 decoded.
    """
    try:
        _ = context.decoded_image
    except binascii.Error as exc:
        _LOGGER.warning('Image data cannot be base64 decoded: "%s"', exc)
        raise FailError(status_code=HTTPStatus.UNPROCESSABLE_ENTITY) from exc


@beartype
def validate_image_is_image(*, context: ValidatorContext) -> None:
    """Validate that the given image data is actually an image file.

    Args:
        context: The context of the request.

    Raises:
        BadImageError: Image data is given and it is not an image file.
    """
    decoded = context.decoded_image
    if decoded is None:
        return

    image_file = io.BytesIO(initial_bytes=decoded)

    try:
        with open_image(fp=image_file) as _:
            pass
    except OSError as exc:
        _LOGGER.warning(msg="The image is not an image file.")
        raise BadImageError from exc


@beartype
def validate_image_format(*, context: ValidatorContext) -> None:
    """Validate the format of the image given to a VWS endpoint.

    Args:
        context: The context of the request.

    Raises:
        BadImageError:  The image is given and is not either a PNG or a JPEG.
    """
    decoded = context.decoded_image
    if decoded is None:
        return

    image_file = io.BytesIO(initial_bytes=decoded)
    with open_image(fp=image_file) as pil_image:
        if pil_image.format in {"PNG", "JPEG"}:
            return

    _LOGGER.warning(msg="The image is not a PNG or JPEG.")
    raise BadImageError


@beartype
def validate_image_color_space(*, context: ValidatorContext) -> None:
    """Validate the color space of the image given to a VWS endpoint.

    Args:
        context: The context of the request.

    Raises:
        BadImageError: The image is given and is not in either the RGB or
            greyscale color space.
    """
    decoded = context.decoded_image
    if decoded is None:
        return

    image_file = io.BytesIO(initial_bytes=decoded)
    with open_image(fp=image_file) as pil_image:
        if pil_image.mode in {"L", "RGB"}:
            return

    _LOGGER.warning(
        msg="The image is not in the RGB or greyscale color space.",
    )
    raise BadImageError


@beartype
def validate_image_size(*, context: ValidatorContext) -> None:
    """Validate the file size of the image given to a VWS endpoint.

    Args:
        context: The context of the request.

    Raises:
        ImageTooLargeError:  The image is given and is not under a certain file
            size threshold.
    """
    decoded = context.decoded_image
    if decoded is None:
        return

    max_allowed_size = 2_359_293
    if len(decoded) <= max_allowed_size:
        return

    _LOGGER.warning(msg="The image is too large.")
    raise ImageTooLargeError


@beartype
def validate_image_pixel_count(*, context: ValidatorContext) -> None:
    """Validate the number of pixels of the image given to a VWS endpoint.

    A small file can decode to a very large number of pixels, so this is not
    covered by the file size limit.

    Args:
        context: The context of the request.

    Raises:
        ImageTooLargeError: The image is given and it has more than the
            maximum number of pixels.
    """
    decoded = context.decoded_image
    if decoded is None:
        return

    image_file = io.BytesIO(initial_bytes=decoded)

    # This limit is not documented.
    # It was found by binary search against a real database, and it holds
    # whatever the image's aspect ratio and color space are.
    max_allowed_pixels = 37_748_736
    with open_image(fp=image_file) as pil_image:
        if pil_image.width * pil_image.height <= max_allowed_pixels:
            return

    _LOGGER.warning(msg="The image has too many pixels.")
    raise ImageTooLargeError


@beartype
def validate_image_integrity(*, context: ValidatorContext) -> None:
    """Validate the integrity of the image given to a VWS endpoint.

    Args:
        context: The context of the request.

    Raises:
        BadImageError: The image is given and is not a valid image file.
    """
    decoded = context.decoded_image
    if decoded is None:
        return

    image_file = io.BytesIO(initial_bytes=decoded)
    with open_image(fp=image_file) as pil_image:
        try:
            pil_image.verify()
        except (OSError, SyntaxError) as exc:
            # ``verify`` raises ``SyntaxError`` for a damaged header and
            # ``OSError`` for damaged image data, such as a PNG which is
            # truncated before its ``IEND`` chunk.
            # ``open_image`` runs outside this ``try``, so anything which
            # cannot be opened at all is already rejected by
            # ``validate_image_is_image``.
            _LOGGER.warning(msg="The image is not a valid image file.")
            raise BadImageError from exc
