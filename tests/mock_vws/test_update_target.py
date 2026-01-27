"""Tests for the mock of the update target endpoint."""

import base64
import io
import json
import uuid
from http import HTTPMethod, HTTPStatus
from typing import TYPE_CHECKING, Any, Final

import pytest
from vws.exceptions.base_exceptions import VWSError
from vws.exceptions.vws_exceptions import (
    AuthenticationFailureError,
    BadImageError,
    FailError,
    ImageTooLargeError,
    MetadataTooLargeError,
    ProjectInactiveError,
    TargetNameExistError,
    TargetStatusNotSuccessError,
)
from vws.reports import TargetStatuses

from mock_vws._constants import ResultCodes
from tests.mock_vws.utils import make_image_file
from tests.mock_vws.utils.assertions import (
    assert_vws_failure,
    assert_vws_response,
)

if TYPE_CHECKING:
    from vws import VWS
    from vws.response import Response

_MAX_METADATA_BYTES: Final[int] = 1024 * 1024 - 1


def _update_target(
    *,
    vws_client: VWS,
    data: dict[str, Any],
    target_id: str,
    content_type: str = "application/json",
) -> Response:
    """Make a request to the endpoint to update a target.

    Args:
        vws_client: The client to use to connect to Vuforia.
        data: The data to send, in JSON format, to the endpoint.
        target_id: The ID of the target to update.
        content_type: The `Content-Type` header to use.

    Returns:
        The response returned by the API.
    """
    content = json.dumps(obj=data).encode(encoding="utf-8")
    return vws_client.make_request(
        method=HTTPMethod.PUT,
        data=content,
        request_path=f"/targets/{target_id}",
        expected_result_code=ResultCodes.SUCCESS.value,
        content_type=content_type,
    )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestUpdate:
    """Tests for updating targets."""

    @staticmethod
    @pytest.mark.parametrize(
        argnames="content_type",
        argvalues=[
            # This is the documented required content type:
            "application/json",
            # Other content types also work.
            "other/content_type",
        ],
        ids=["Documented Content-Type", "Undocumented Content-Type"],
    )
    def test_content_types(
        vws_client: VWS,
        image_file_failed_state: io.BytesIO,
        content_type: str,
    ) -> None:
        """
        The ``Content-Type`` header does not change the response as long
        as it
        is not empty.
        """
        target_id = vws_client.add_target(
            name="example",
            width=1,
            image=image_file_failed_state,
            active_flag=True,
            application_metadata=None,
        )

        with pytest.raises(
            expected_exception=TargetStatusNotSuccessError
        ) as exc:
            _update_target(
                vws_client=vws_client,
                data={"name": "Adam"},
                target_id=target_id,
                content_type=content_type,
            )

        # Code is FORBIDDEN because the target is processing.
        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.FORBIDDEN,
            result_code=ResultCodes.TARGET_STATUS_NOT_SUCCESS,
        )

    @staticmethod
    def test_empty_content_type(
        vws_client: VWS,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        An ``UNAUTHORIZED`` response is given if an empty ``Content-
        Type``
        header is given.
        """
        target_id = vws_client.add_target(
            name="example",
            width=1,
            image=image_file_failed_state,
            active_flag=True,
            application_metadata=None,
        )

        with pytest.raises(
            expected_exception=AuthenticationFailureError
        ) as exc:
            _update_target(
                vws_client=vws_client,
                data={"name": "Adam"},
                target_id=target_id,
                content_type="",
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.UNAUTHORIZED,
            result_code=ResultCodes.AUTHENTICATION_FAILURE,
        )

    @staticmethod
    def test_no_fields_given(
        vws_client: VWS,
        target_id: str,
    ) -> None:
        """No data fields are required."""
        vws_client.wait_for_target_processed(target_id=target_id)

        response = _update_target(
            vws_client=vws_client,
            data={},
            target_id=target_id,
        )

        assert_vws_response(
            response=response,
            status_code=HTTPStatus.OK,
            result_code=ResultCodes.SUCCESS,
        )

        response_json = json.loads(s=response.text)
        assert isinstance(response_json, dict)
        assert response_json.keys() == {"result_code", "transaction_id"}

        target_details = vws_client.get_target_record(target_id=target_id)
        # Targets go back to processing after being updated.
        assert target_details.status == TargetStatuses.PROCESSING

        vws_client.wait_for_target_processed(target_id=target_id)

        target_details = vws_client.get_target_record(target_id=target_id)
        assert target_details.status == TargetStatuses.SUCCESS


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestUnexpectedData:
    """Tests for passing data which is not allowed to the endpoint."""

    @staticmethod
    def test_invalid_extra_data(
        vws_client: VWS,
        target_id: str,
    ) -> None:
        """
        A `BAD_REQUEST` response is returned when unexpected data is
        given.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        with pytest.raises(expected_exception=FailError) as exc:
            _update_target(
                vws_client=vws_client,
                data={"extra_thing": 1},
                target_id=target_id,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestWidth:
    """Tests for the target width field."""

    @staticmethod
    @pytest.mark.parametrize(
        argnames="width",
        argvalues=[-1, "10", None, 0],
        ids=["Negative", "Wrong Type", "None", "Zero"],
    )
    def test_width_invalid(
        vws_client: VWS,
        width: int | str | None,
        target_id: str,
    ) -> None:
        """The width must be a number greater than zero."""
        vws_client.wait_for_target_processed(target_id=target_id)

        target_details = vws_client.get_target_record(target_id=target_id)
        original_width = target_details.target_record.width

        with pytest.raises(expected_exception=FailError) as exc:
            _update_target(
                vws_client=vws_client,
                data={"width": width},
                target_id=target_id,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )

        target_details = vws_client.get_target_record(target_id=target_id)
        assert target_details.target_record.width == original_width

    @staticmethod
    def test_width_valid(vws_client: VWS, target_id: str) -> None:
        """Positive numbers are valid widths."""
        vws_client.wait_for_target_processed(target_id=target_id)

        width = 0.01
        vws_client.update_target(target_id=target_id, width=width)
        target_details = vws_client.get_target_record(target_id=target_id)
        assert target_details.target_record.width == width


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestActiveFlag:
    """Tests for the active flag parameter."""

    @staticmethod
    @pytest.mark.parametrize(
        argnames="initial_active_flag",
        argvalues=[True, False],
    )
    @pytest.mark.parametrize(
        argnames="desired_active_flag",
        argvalues=[True, False],
    )
    def test_active_flag(
        vws_client: VWS,
        image_file_success_state_low_rating: io.BytesIO,
        *,
        initial_active_flag: bool,
        desired_active_flag: bool,
    ) -> None:
        """Setting the active flag to a Boolean value changes it."""
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=image_file_success_state_low_rating,
            active_flag=initial_active_flag,
            application_metadata=None,
        )

        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.update_target(
            target_id=target_id,
            active_flag=desired_active_flag,
        )

        target_details = vws_client.get_target_record(target_id=target_id)
        assert target_details.target_record.active_flag == desired_active_flag

    @staticmethod
    @pytest.mark.parametrize(
        argnames="desired_active_flag",
        argvalues=["string", None],
    )
    def test_invalid(
        vws_client: VWS,
        target_id: str,
        desired_active_flag: str | None,
    ) -> None:
        """
        Values which are not Boolean values are not valid active
        flags.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        with pytest.raises(expected_exception=FailError) as exc:
            _update_target(
                vws_client=vws_client,
                data={"active_flag": desired_active_flag},
                target_id=target_id,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestApplicationMetadata:
    """Tests for the application metadata parameter."""

    @staticmethod
    @pytest.mark.parametrize(
        argnames="metadata",
        argvalues=[
            b"a",
            b"a" * _MAX_METADATA_BYTES,
        ],
        ids=["Short", "Max length"],
    )
    def test_base64_encoded(
        target_id: str,
        metadata: bytes,
        vws_client: VWS,
    ) -> None:
        """A base64 encoded string is valid application metadata."""
        metadata_encoded = base64.b64encode(s=metadata).decode(
            encoding="ascii"
        )
        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.update_target(
            target_id=target_id,
            application_metadata=metadata_encoded,
        )

    @staticmethod
    @pytest.mark.parametrize(argnames="invalid_metadata", argvalues=[1, None])
    def test_invalid_type(
        vws_client: VWS,
        target_id: str,
        invalid_metadata: int | None,
    ) -> None:
        """Non-string values cannot be given as valid application metadata."""
        vws_client.wait_for_target_processed(target_id=target_id)

        with pytest.raises(expected_exception=FailError) as exc:
            _update_target(
                vws_client=vws_client,
                data={"application_metadata": invalid_metadata},
                target_id=target_id,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )

    @staticmethod
    def test_not_base64_encoded_processable(
        vws_client: VWS,
        target_id: str,
        not_base64_encoded_processable: str,
    ) -> None:
        """
        Some strings which are not valid base64 encoded strings are
        allowed as
        application metadata.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        vws_client.update_target(
            target_id=target_id,
            application_metadata=not_base64_encoded_processable,
        )

    @staticmethod
    def test_not_base64_encoded_not_processable(
        vws_client: VWS,
        target_id: str,
        not_base64_encoded_not_processable: str,
    ) -> None:
        """
        Some strings which are not valid base64 encoded strings are not
        allowed
        as application metadata.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        with pytest.raises(expected_exception=FailError) as exc:
            vws_client.update_target(
                target_id=target_id,
                application_metadata=not_base64_encoded_not_processable,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.FAIL,
        )

    @staticmethod
    def test_metadata_too_large(vws_client: VWS, target_id: str) -> None:
        """
        A base64 encoded string of greater than 1024 * 1024 bytes is too
        large
        for application metadata.
        """
        metadata = b"a" * (_MAX_METADATA_BYTES + 1)
        metadata_encoded = base64.b64encode(s=metadata).decode(
            encoding="ascii"
        )
        vws_client.wait_for_target_processed(target_id=target_id)

        with pytest.raises(expected_exception=MetadataTooLargeError) as exc:
            vws_client.update_target(
                target_id=target_id,
                application_metadata=metadata_encoded,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.METADATA_TOO_LARGE,
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestTargetName:
    """Tests for the target name field."""

    _MAX_CHAR_VALUE = 65535
    _MAX_NAME_LENGTH = 64

    @staticmethod
    @pytest.mark.parametrize(
        argnames="name",
        argvalues=[
            "á",
            # We test just below the max character value.
            # This is because targets with the max character value in their
            # names get stuck in the processing stage.
            chr(_MAX_CHAR_VALUE - 2),
            "a" * _MAX_NAME_LENGTH,
        ],
        ids=["Short name", "Max char value", "Long name"],
    )
    def test_name_valid(
        name: str,
        target_id: str,
        vws_client: VWS,
    ) -> None:
        """A target's name must be a string of length 0 < N < 65.

        We test characters out of range in another test as that gives a
        different error.
        """
        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.update_target(target_id=target_id, name=name)
        target_details = vws_client.get_target_record(target_id=target_id)
        assert target_details.target_record.name == name

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("name", "status_code", "result_code"),
        argvalues=[
            (1, HTTPStatus.BAD_REQUEST, ResultCodes.FAIL),
            ("", HTTPStatus.BAD_REQUEST, ResultCodes.FAIL),
            (
                "a" * (_MAX_NAME_LENGTH + 1),
                HTTPStatus.BAD_REQUEST,
                ResultCodes.FAIL,
            ),
            (None, HTTPStatus.BAD_REQUEST, ResultCodes.FAIL),
            (
                chr(_MAX_CHAR_VALUE + 1),
                HTTPStatus.FORBIDDEN,
                ResultCodes.TARGET_NAME_EXIST,
            ),
            (
                chr(_MAX_CHAR_VALUE + 1) * (_MAX_NAME_LENGTH + 1),
                HTTPStatus.BAD_REQUEST,
                ResultCodes.FAIL,
            ),
        ],
        ids=[
            "Wrong Type",
            "Empty",
            "Too Long",
            "None",
            "Bad char",
            "Bad char too long",
        ],
    )
    def test_name_invalid(
        name: str | int | None,
        target_id: str,
        vws_client: VWS,
        status_code: int,
        result_code: ResultCodes,
    ) -> None:
        """A target's name must be a string of length 0 < N < 65."""
        vws_client.wait_for_target_processed(target_id=target_id)

        with pytest.raises(expected_exception=VWSError) as exc:
            _update_target(
                vws_client=vws_client,
                data={"name": name},
                target_id=target_id,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=status_code,
            result_code=result_code,
        )

    @staticmethod
    def test_existing_target_name(
        image_file_success_state_low_rating: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """Only one target can have a given name."""
        first_target_name = "example_name"
        second_target_name = "another_example_name"

        first_target_id = vws_client.add_target(
            name=first_target_name,
            width=1,
            image=image_file_success_state_low_rating,
            active_flag=True,
            application_metadata=None,
        )

        second_target_id = vws_client.add_target(
            name=second_target_name,
            width=1,
            image=image_file_success_state_low_rating,
            active_flag=True,
            application_metadata=None,
        )

        vws_client.wait_for_target_processed(target_id=first_target_id)
        vws_client.wait_for_target_processed(target_id=second_target_id)

        with pytest.raises(expected_exception=TargetNameExistError) as exc:
            vws_client.update_target(
                target_id=second_target_id,
                name=first_target_name,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.FORBIDDEN,
            result_code=ResultCodes.TARGET_NAME_EXIST,
        )

    @staticmethod
    def test_same_name_given(
        image_file_success_state_low_rating: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """Updating a target with its own name does not give an error."""
        name = "example"

        target_id = vws_client.add_target(
            name=name,
            width=1,
            image=image_file_success_state_low_rating,
            active_flag=True,
            application_metadata=None,
        )

        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.update_target(target_id=target_id, name=name)
        target_details = vws_client.get_target_record(target_id=target_id)
        assert target_details.target_record.name == name


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestImage:
    """Tests for the image parameter.

    The specification for images is documented at
    https://library.vuforia.com/features/images/image-targets.html.
    """

    @staticmethod
    def test_image_valid(
        image_files_failed_state: io.BytesIO,
        target_id: str,
        vws_client: VWS,
    ) -> None:
        """
        JPEG and PNG files in the RGB and greyscale color spaces are
        allowed.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        vws_client.update_target(
            target_id=target_id,
            image=image_files_failed_state,
        )

    @staticmethod
    def test_bad_image_format_or_color_space(
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
        vws_client.wait_for_target_processed(target_id=target_id)
        with pytest.raises(expected_exception=BadImageError) as exc:
            vws_client.update_target(target_id=target_id, image=bad_image_file)

        status_code = exc.value.response.status_code
        assert status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    @staticmethod
    def test_corrupted(
        vws_client: VWS,
        corrupted_image_file: io.BytesIO,
        target_id: str,
    ) -> None:
        """An error is returned when the given image is corrupted."""
        vws_client.wait_for_target_processed(target_id=target_id)
        with pytest.raises(expected_exception=BadImageError) as exc:
            vws_client.update_target(
                target_id=target_id,
                image=corrupted_image_file,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.BAD_IMAGE,
        )

    @staticmethod
    def test_image_too_large(target_id: str, vws_client: VWS) -> None:
        """
        An `ImageTooLargeError` result is returned if the image is above
        a
        certain threshold.
        """
        max_bytes = 2.3 * 1024 * 1024
        width = height = 886
        png_not_too_large = make_image_file(
            file_format="PNG",
            color_space="RGB",
            width=width,
            height=height,
        )

        vws_client.wait_for_target_processed(target_id=target_id)

        image_data = png_not_too_large.getvalue()
        image_content_size = len(image_data)
        # We check that the image we created is just slightly smaller than the
        # maximum file size.
        #
        # This is just because of the implementation details of
        # ``max_image_file``.
        assert image_content_size < max_bytes
        assert (image_content_size * 1.05) > max_bytes

        vws_client.update_target(target_id=target_id, image=png_not_too_large)

        vws_client.wait_for_target_processed(target_id=target_id)

        width = width + 1
        height = height + 1
        png_too_large = make_image_file(
            file_format="PNG",
            color_space="RGB",
            width=width,
            height=height,
        )

        image_data = png_too_large.getvalue()
        image_content_size = len(image_data)
        # We check that the image we created is just slightly smaller than the
        # maximum file size.
        #
        # This is just because of the implementation details of
        # ``max_image_file``.
        assert image_content_size < max_bytes
        assert (image_content_size * 1.05) > max_bytes

        with pytest.raises(expected_exception=ImageTooLargeError) as exc:
            vws_client.update_target(target_id=target_id, image=png_too_large)

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.IMAGE_TOO_LARGE,
        )

    @staticmethod
    def test_not_base64_encoded_processable(
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
        vws_client.wait_for_target_processed(target_id=target_id)

        with pytest.raises(expected_exception=BadImageError) as exc:
            _update_target(
                vws_client=vws_client,
                data={"image": not_base64_encoded_processable},
                target_id=target_id,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.BAD_IMAGE,
        )

    @staticmethod
    def test_not_base64_encoded_not_processable(
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
        vws_client.wait_for_target_processed(target_id=target_id)

        with pytest.raises(expected_exception=FailError) as exc:
            _update_target(
                vws_client=vws_client,
                data={"image": not_base64_encoded_not_processable},
                target_id=target_id,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.FAIL,
        )

    @staticmethod
    def test_not_image(target_id: str, vws_client: VWS) -> None:
        """
        If the given image is not an image file then a `BadImageError`
        result
        is returned.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        with pytest.raises(expected_exception=BadImageError) as exc:
            vws_client.update_target(
                target_id=target_id,
                image=io.BytesIO(initial_bytes=b"not_image_data"),
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.BAD_IMAGE,
        )

    @staticmethod
    @pytest.mark.parametrize(
        argnames="invalid_type_image",
        argvalues=[1, None],
    )
    def test_invalid_type(
        invalid_type_image: int | None,
        target_id: str,
        vws_client: VWS,
    ) -> None:
        """If the given image is not a string, a `Fail` result is returned."""
        vws_client.wait_for_target_processed(target_id=target_id)

        with pytest.raises(expected_exception=FailError) as exc:
            _update_target(
                vws_client=vws_client,
                data={"image": invalid_type_image},
                target_id=target_id,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )

    @staticmethod
    def test_rating_can_change(
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


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestInactiveProject:
    """Tests for inactive projects."""

    @staticmethod
    def test_inactive_project(inactive_vws_client: VWS) -> None:
        """
        If the project is inactive, a FORBIDDEN response is
        returned.
        """
        with pytest.raises(expected_exception=ProjectInactiveError):
            inactive_vws_client.update_target(target_id=uuid.uuid4().hex)
