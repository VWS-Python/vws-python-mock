"""Tests for the image parameter.

The specification for images is documented at
https://library.vuforia.com/features/images/image-targets.html.
"""

import io
import uuid
from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    BadImageError,
    FailError,
    ImageTooLargeError,
)
from vws.reports import TargetStatuses
from vws_test_fixtures.images import VWS_MAX_IMAGE_FILE_SIZE

from vws_mock_contract_tests.update_target.helpers import (
    update_target,
)
from vws_mock_contract_tests.utils import make_truncated_png_file
from vws_mock_contract_tests.utils.assertions import (
    assert_vws_failure,
)


def test_image_valid(
    *,
    image_files_failed_state: io.BytesIO,
    target_id: str,
    vws_client: VWS,
) -> None:
    """
    JPEG and PNG files in the RGB and greyscale color spaces are
    allowed.
    """
    vws_client.update_target(
        target_id=target_id,
        image=image_files_failed_state,
    )


def test_bad_image_format_or_color_space(
    *,
    bad_image_file: io.BytesIO,
    target_id: str,
    vws_client: VWS,
) -> None:
    """
    A `BAD_IMAGE` response is returned if an image which is not a
    JPEG or
    PNG file is given, or if the given image is not in the greyscale or
    RGB
    color space.
    """
    with pytest.raises(expected_exception=BadImageError) as exc:
        vws_client.update_target(target_id=target_id, image=bad_image_file)

    status_code = exc.value.response.status_code
    assert status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_corrupted(
    *,
    vws_client: VWS,
    corrupted_image_file: io.BytesIO,
    target_id: str,
) -> None:
    """An error is returned when the given image is corrupted."""
    with pytest.raises(expected_exception=BadImageError) as exc:
        vws_client.update_target(
            target_id=target_id,
            image=corrupted_image_file,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="BadImage",
    )


def test_truncated(
    *,
    vws_client: VWS,
    target_id: str,
) -> None:
    """
    An error is returned when the given image is truncated before
    the
    end of its image data.
    """
    image_file = make_truncated_png_file()

    with pytest.raises(expected_exception=BadImageError) as exc:
        vws_client.update_target(
            target_id=target_id,
            image=image_file,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="BadImage",
    )


def test_image_too_large(
    *,
    target_id: str,
    vws_client: VWS,
    png_just_under_max_size: io.BytesIO,
    png_too_large: io.BytesIO,
) -> None:
    """
    An `ImageTooLargeError` result is returned if the image is above
    a
    certain threshold.
    """
    max_bytes = VWS_MAX_IMAGE_FILE_SIZE

    image_content_size = len(png_just_under_max_size.getvalue())
    assert image_content_size < max_bytes
    assert (image_content_size * 1.05) > max_bytes

    vws_client.update_target(
        target_id=target_id,
        image=png_just_under_max_size,
    )

    vws_client.wait_for_target_processed(target_id=target_id)

    image_content_size = len(png_too_large.getvalue())
    assert image_content_size > max_bytes

    with pytest.raises(expected_exception=ImageTooLargeError) as exc:
        vws_client.update_target(target_id=target_id, image=png_too_large)

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="ImageTooLarge",
    )


def test_not_base64_encoded_processable(
    *,
    vws_client: VWS,
    target_id: str,
    not_base64_encoded_processable: str,
) -> None:
    """Some strings which are not valid base64 encoded strings are
    allowed
    as an image without getting a "Fail" response.

    This is because Vuforia treats them as valid base64, but then
    not a valid image.
    """
    with pytest.raises(expected_exception=BadImageError) as exc:
        _ = update_target(
            vws_client=vws_client,
            data={"image": not_base64_encoded_processable},
            target_id=target_id,
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
    target_id: str,
    not_base64_encoded_not_processable: str,
) -> None:
    """
    Some strings which are not valid base64 encoded strings are not
    processable by Vuforia, and then when given as an image Vuforia
    returns
    a "Fail" response.
    """
    with pytest.raises(expected_exception=FailError) as exc:
        _ = update_target(
            vws_client=vws_client,
            data={"image": not_base64_encoded_not_processable},
            target_id=target_id,
            content_type="application/json",
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="Fail",
    )


def test_not_image(*, target_id: str, vws_client: VWS) -> None:
    """
    If the given image is not an image file then a `BadImageError`
    result
    is returned.
    """
    with pytest.raises(expected_exception=BadImageError) as exc:
        vws_client.update_target(
            target_id=target_id,
            image=io.BytesIO(initial_bytes=b"not_image_data"),
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
    target_id: str,
    vws_client: VWS,
) -> None:
    """If the given image is not a string, a `Fail` result is returned."""
    with pytest.raises(expected_exception=FailError) as exc:
        _ = update_target(
            vws_client=vws_client,
            data={"image": invalid_type_image},
            target_id=target_id,
            content_type="application/json",
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.BAD_REQUEST,
        result_code="Fail",
    )


def test_rating_does_not_return_to_minus_one(
    *,
    image_file_success_state_low_rating: io.BytesIO,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
) -> None:
    """An update does not start a new -1 tracking rating window.

    A target reports a rating of -1 for a short time after it is
    uploaded, and then the image's rating, while it is still
    processing. An update returns the target to the processing
    state, but the rating does not go back to -1: the new image's
    rating is reported straight away.

    Anyone who polls for an update to be processed by watching the
    rating leave -1, rather than by watching the status, would wait
    forever, so the mock must not offer them a window which the real
    Vuforia does not have.
    """
    target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_file_success_state_low_rating,
        active_flag=True,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=target_id)

    vws_client.update_target(target_id=target_id, image=high_quality_image)

    target_details = vws_client.get_target_record(target_id=target_id)
    assert target_details.target_record.tracking_rating in range(6)


def test_rating_can_change(
    *,
    image_file_success_state_low_rating: io.BytesIO,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
) -> None:
    """If the target is updated with an image of different quality, the
    tracking rating can change.

    "quality" refers to Vuforia's internal rating system. The mock
    randomly assigns a quality and makes sure that the new quality
    is different to the old quality.
    """
    target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_file_success_state_low_rating,
        active_flag=True,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=target_id)

    target_details = vws_client.get_target_record(target_id=target_id)
    assert target_details.status == TargetStatuses.SUCCESS
    # Tracking rating is between 0 and 5 when status is 'success'
    original_tracking_rating = target_details.target_record.tracking_rating
    assert original_tracking_rating in range(6)

    vws_client.update_target(target_id=target_id, image=high_quality_image)

    vws_client.wait_for_target_processed(target_id=target_id)
    target_details = vws_client.get_target_record(target_id=target_id)
    assert target_details.status == TargetStatuses.SUCCESS
    # Tracking rating is between 0 and 5 when status is 'success'
    new_tracking_rating = target_details.target_record.tracking_rating
    assert new_tracking_rating in range(6)

    assert original_tracking_rating != new_tracking_rating
