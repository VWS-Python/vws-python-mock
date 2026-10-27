"""Tests for the image parameter.

The specification for images is documented at
https://library.vuforia.com/features/images/image-targets.html.
"""

import io
from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    BadImageError,
    FailError,
    ImageTooLargeError,
)
from vws_test_fixtures.images import VWS_MAX_IMAGE_FILE_SIZE

from tests.mock_vws.add_target.helpers import (
    add_target_to_vws,
)
from tests.mock_vws.utils import (
    make_decompression_bomb_image_file,
    make_single_color_image_file,
    make_truncated_png_file,
)
from tests.mock_vws.utils.assertions import (
    assert_vws_failure,
)


def test_image_valid(
    *,
    vws_client: VWS,
    image_files_failed_state: io.BytesIO,
) -> None:
    """
    JPEG and PNG files in the RGB and greyscale color spaces are
    allowed.
    """
    _ = vws_client.add_target(
        name="example_name",
        width=1,
        image=image_files_failed_state,
        application_metadata=None,
        active_flag=True,
    )


def test_bad_image_format_or_color_space(
    *,
    bad_image_file: io.BytesIO,
    vws_client: VWS,
) -> None:
    """
    An `UNPROCESSABLE_ENTITY` response is returned if an image which
    is not
    a JPEG or PNG file is given, or if the given image is not in the
    greyscale or RGB color space.
    """
    with pytest.raises(expected_exception=BadImageError) as exc:
        _ = vws_client.add_target(
            name="example_name",
            width=1,
            image=bad_image_file,
            application_metadata=None,
            active_flag=True,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="BadImage",
    )


def test_corrupted(
    *,
    corrupted_image_file: io.BytesIO,
    vws_client: VWS,
) -> None:
    """An error is returned when the given image is corrupted."""
    with pytest.raises(expected_exception=BadImageError) as exc:
        _ = vws_client.add_target(
            name="example_name",
            width=1,
            image=corrupted_image_file,
            application_metadata=None,
            active_flag=True,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="BadImage",
    )


def test_truncated(vws_client: VWS) -> None:
    """
    An error is returned when the given image is truncated before
    the
    end of its image data.
    """
    image_file = make_truncated_png_file()

    with pytest.raises(expected_exception=BadImageError) as exc:
        _ = vws_client.add_target(
            name="example_name",
            width=1,
            image=image_file,
            application_metadata=None,
            active_flag=True,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="BadImage",
    )


def test_decompression_bomb(vws_client: VWS) -> None:
    """
    An ``ImageTooLargeError`` result is returned when the given
    image has a small file size but a huge number of pixels.
    """
    max_bytes = 2.3 * 1024 * 1024
    image_file = make_decompression_bomb_image_file()
    assert len(image_file.getvalue()) < max_bytes

    with pytest.raises(expected_exception=ImageTooLargeError) as exc:
        _ = vws_client.add_target(
            name="example_name",
            width=1,
            image=image_file,
            application_metadata=None,
            active_flag=True,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="ImageTooLarge",
    )


def test_image_pixel_count_too_large(
    *,
    vws_client: VWS,
    pixel_count_too_large: io.BytesIO,
) -> None:
    """
    An ``ImageTooLargeError`` result is returned if the image has
    more than 37748736 pixels, whatever its file size.

    This limit is not documented.
    """
    max_allowed_pixels = 37_748_736
    width = height = 6144
    assert width * height == max_allowed_pixels

    image_not_too_many_pixels = make_single_color_image_file(
        width=width,
        height=height,
    )

    _ = vws_client.add_target(
        name="example_name",
        width=1,
        image=image_not_too_many_pixels,
        application_metadata=None,
        active_flag=True,
    )

    with pytest.raises(expected_exception=ImageTooLargeError) as exc:
        _ = vws_client.add_target(
            name="example_name_2",
            width=1,
            image=pixel_count_too_large,
            application_metadata=None,
            active_flag=True,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="ImageTooLarge",
    )


def test_image_file_size_too_large(
    *,
    vws_client: VWS,
    png_just_under_max_size: io.BytesIO,
    png_too_large: io.BytesIO,
) -> None:
    """
    An ``ImageTooLargeError`` result is returned if the image file
    size is
    above a certain threshold.
    """
    max_bytes = VWS_MAX_IMAGE_FILE_SIZE

    image_content_size = len(png_just_under_max_size.getvalue())
    assert image_content_size < max_bytes
    assert (image_content_size * 1.05) > max_bytes

    _ = vws_client.add_target(
        name="example_name",
        width=1,
        image=png_just_under_max_size,
        application_metadata=None,
        active_flag=True,
    )

    image_content_size = len(png_too_large.getvalue())
    assert image_content_size > max_bytes

    with pytest.raises(expected_exception=ImageTooLargeError) as exc:
        _ = vws_client.add_target(
            name="example_name_2",
            width=1,
            image=png_too_large,
            application_metadata=None,
            active_flag=True,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="ImageTooLarge",
    )


def test_not_base64_encoded_processable(
    *,
    vws_client: VWS,
    not_base64_encoded_processable: str,
) -> None:
    """Some strings which are not valid base64 encoded strings are
    allowed
    as an image without getting a "Fail" response.

    This is because Vuforia treats them as valid base64, but then
    not a valid image.
    """
    data = {
        "name": "example_name",
        "width": 1,
        "image": not_base64_encoded_processable,
    }

    with pytest.raises(expected_exception=BadImageError) as exc:
        _ = add_target_to_vws(
            vws_client=vws_client,
            data=data,
            content_type="application/json",
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="BadImage",
    )


def test_not_base64_encoded_not_processable(
    *,
    vws_client: VWS,
    not_base64_encoded_not_processable: str,
) -> None:
    """
    Some strings which are not valid base64 encoded strings are not
    processable by Vuforia, and then when given as an image Vuforia
    returns
    a "Fail" response.
    """
    data = {
        "name": "example_name",
        "width": 1,
        "image": not_base64_encoded_not_processable,
    }

    with pytest.raises(expected_exception=FailError) as exc:
        _ = add_target_to_vws(
            vws_client=vws_client,
            data=data,
            content_type="application/json",
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="Fail",
    )


def test_not_image(vws_client: VWS) -> None:
    """
    If the given image is not an image file then a `BadImageError`
    result
    is returned.
    """
    with pytest.raises(expected_exception=BadImageError) as exc:
        _ = vws_client.add_target(
            name="example_name",
            width=1,
            image=io.BytesIO(initial_bytes=b"not_image_data"),
            application_metadata=None,
            active_flag=True,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="BadImage",
    )


@pytest.mark.parametrize(
    argnames="invalid_type_image",
    argvalues=[1, None],
)
def test_invalid_type(
    *,
    invalid_type_image: int | None,
    vws_client: VWS,
) -> None:
    """If the given image is not a string, a `Fail` result is returned."""
    data = {
        "name": "example_name",
        "width": 1,
        "image": invalid_type_image,
    }

    with pytest.raises(expected_exception=FailError) as exc:
        _ = add_target_to_vws(
            vws_client=vws_client,
            data=data,
            content_type="application/json",
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.BAD_REQUEST,
        result_code="Fail",
    )
