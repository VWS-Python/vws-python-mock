"""
Tests for the mock of the update target endpoint.
"""

from __future__ import annotations

import base64
import json
import uuid
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import urljoin

import pytest
import requests
from mock_vws._constants import ResultCodes
from requests_mock import PUT
from vws.exceptions.vws_exceptions import BadImage, ProjectInactive
from vws.reports import TargetStatuses
from vws_auth_tools import authorization_header, rfc_1123_date

from tests.mock_vws.utils import make_image_file
from tests.mock_vws.utils.assertions import (
    assert_vws_failure,
    assert_vws_response,
)

_MAX_METADATA_BYTES: Final[int] = 1024 * 1024 - 1

if TYPE_CHECKING:
    import io

    from mock_vws.database import VuforiaDatabase
    from vws import VWS


def update_target(
    vuforia_database: VuforiaDatabase,
    data: dict[str, Any],
    target_id: str,
    content_type: str = "application/json",
) -> requests.Response:
    """
    Make a request to the endpoint to update a target.

    Args:
        vuforia_database: The credentials to use to connect to
            Vuforia.
        data: The data to send, in JSON format, to the endpoint.
        target_id: The ID of the target to update.
        content_type: The `Content-Type` header to use.

    Returns:
        The response returned by the API.
    """
    date = rfc_1123_date()
    request_path = "/targets/" + target_id

    content = bytes(json.dumps(data), encoding="utf-8")

    authorization_string = authorization_header(
        access_key=vuforia_database.server_access_key,
        secret_key=vuforia_database.server_secret_key,
        method=PUT,
        content=content,
        content_type=content_type,
        date=date,
        request_path=request_path,
    )

    headers = {
        "Authorization": authorization_string,
        "Date": date,
        "Content-Type": content_type,
    }

    return requests.request(
        method=PUT,
        url=urljoin("https://vws.vuforia.com/", request_path),
        headers=headers,
        data=content,
        timeout=30,
    )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestUpdate:
    """
    Tests for updating targets.
    """

    @staticmethod
    @pytest.mark.parametrize(
        "content_type",
        [
            # This is the documented required content type:
            "application/json",
            # Other content types also work.
            "other/content_type",
        ],
        ids=["Documented Content-Type", "Undocumented Content-Type"],
    )
    def test_content_types(
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
        image_file_failed_state: io.BytesIO,
        content_type: str,
    ) -> None:
        """
        The ``Content-Type`` header does not change the response as long as it
        is not empty.
        """
        target_id = vws_client.add_target(
            name="example",
            width=1,
            image=image_file_failed_state,
            active_flag=True,
            application_metadata=None,
        )

        response = update_target(
            vuforia_database=vuforia_database,
            data={"name": "Adam"},
            target_id=target_id,
            content_type=content_type,
        )

        # Code is FORBIDDEN because the target is processing.
        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.FORBIDDEN,
            result_code=ResultCodes.TARGET_STATUS_NOT_SUCCESS,
        )

    @staticmethod
    def test_empty_content_type(
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        An ``UNAUTHORIZED`` response is given if an empty ``Content-Type``
        header is given.
        """
        target_id = vws_client.add_target(
            name="example",
            width=1,
            image=image_file_failed_state,
            active_flag=True,
            application_metadata=None,
        )

        response = update_target(
            vuforia_database=vuforia_database,
            data={"name": "Adam"},
            target_id=target_id,
            content_type="",
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            result_code=ResultCodes.AUTHENTICATION_FAILURE,
        )

    @staticmethod
    def test_no_fields_given(
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
        target_id: str,
    ) -> None:
        """
        No data fields are required.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        response = update_target(
            vuforia_database=vuforia_database,
            data={},
            target_id=target_id,
        )

        assert_vws_response(
            response=response,
            status_code=HTTPStatus.OK,
            result_code=ResultCodes.SUCCESS,
        )

        assert response.json().keys() == {"result_code", "transaction_id"}

        target_details = vws_client.get_target_record(target_id=target_id)
        # Targets go back to processing after being updated.
        assert target_details.status == TargetStatuses.PROCESSING

        vws_client.wait_for_target_processed(target_id=target_id)

        target_details = vws_client.get_target_record(target_id=target_id)
        assert target_details.status == TargetStatuses.SUCCESS


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestUnexpectedData:
    """
    Tests for passing data which is not allowed to the endpoint.
    """

    @staticmethod
    def test_invalid_extra_data(
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
        target_id: str,
    ) -> None:
        """
        A `BAD_REQUEST` response is returned when unexpected data is given.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        response = update_target(
            vuforia_database=vuforia_database,
            data={"extra_thing": 1},
            target_id=target_id,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestWidth:
    """
    Tests for the target width field.
    """

    @staticmethod
    @pytest.mark.parametrize(
        "width",
        [-1, "10", None, 0],
        ids=["Negative", "Wrong Type", "None", "Zero"],
    )
    def test_width_invalid(
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
        width: int | str | None,
        target_id: str,
    ) -> None:
        """
        The width must be a number greater than zero.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        target_details = vws_client.get_target_record(target_id=target_id)
        original_width = target_details.target_record.width

        response = update_target(
            vuforia_database=vuforia_database,
            data={"width": width},
            target_id=target_id,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )

        target_details = vws_client.get_target_record(target_id=target_id)
        assert target_details.target_record.width == original_width

    @staticmethod
    def test_width_valid(vws_client: VWS, target_id: str) -> None:
        """
        Positive numbers are valid widths.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        width = 0.01
        vws_client.update_target(target_id=target_id, width=width)
        target_details = vws_client.get_target_record(target_id=target_id)
        assert target_details.target_record.width == width


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestActiveFlag:
    """
    Tests for the active flag parameter.
    """

    @staticmethod
    @pytest.mark.parametrize("initial_active_flag", [True, False])
    @pytest.mark.parametrize("desired_active_flag", [True, False])
    def test_active_flag(
        vws_client: VWS,
        image_file_success_state_low_rating: io.BytesIO,
        *,
        initial_active_flag: bool,
        desired_active_flag: bool,
    ) -> None:
        """
        Setting the active flag to a Boolean value changes it.
        """
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
    @pytest.mark.parametrize("desired_active_flag", ["string", None])
    def test_invalid(
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
        target_id: str,
        desired_active_flag: str | None,
    ) -> None:
        """
        Values which are not Boolean values are not valid active flags.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        response = update_target(
            vuforia_database=vuforia_database,
            data={"active_flag": desired_active_flag},
            target_id=target_id,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestApplicationMetadata:
    """
    Tests for the application metadata parameter.
    """

    @staticmethod
    @pytest.mark.parametrize(
        "metadata",
        [
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
        """
        A base64 encoded string is valid application metadata.
        """
        metadata_encoded = base64.b64encode(metadata).decode("ascii")
        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.update_target(
            target_id=target_id,
            application_metadata=metadata_encoded,
        )

    @staticmethod
    @pytest.mark.parametrize("invalid_metadata", [1, None])
    def test_invalid_type(
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
        target_id: str,
        invalid_metadata: int | None,
    ) -> None:
        """
        Non-string values cannot be given as valid application metadata.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        response = update_target(
            vuforia_database=vuforia_database,
            data={"application_metadata": invalid_metadata},
            target_id=target_id,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )

    @staticmethod
    def test_not_base64_encoded_processable(
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
        target_id: str,
        not_base64_encoded_processable: str,
    ) -> None:
        """
        Some strings which are not valid base64 encoded strings are allowed as
        application metadata.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        response = update_target(
            vuforia_database=vuforia_database,
            data={"application_metadata": not_base64_encoded_processable},
            target_id=target_id,
        )

        assert_vws_response(
            response=response,
            status_code=HTTPStatus.OK,
            result_code=ResultCodes.SUCCESS,
        )

    @staticmethod
    def test_not_base64_encoded_not_processable(
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
        target_id: str,
        not_base64_encoded_not_processable: str,
    ) -> None:
        """
        Some strings which are not valid base64 encoded strings are not allowed
        as application metadata.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        response = update_target(
            vuforia_database=vuforia_database,
            data={"application_metadata": not_base64_encoded_not_processable},
            target_id=target_id,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.FAIL,
        )

    @staticmethod
    def test_metadata_too_large(
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
        target_id: str,
    ) -> None:
        """
        A base64 encoded string of greater than 1024 * 1024 bytes is too large
        for application metadata.
        """
        metadata = b"a" * (_MAX_METADATA_BYTES + 1)
        metadata_encoded = base64.b64encode(metadata).decode("ascii")
        vws_client.wait_for_target_processed(target_id=target_id)

        response = update_target(
            vuforia_database=vuforia_database,
            data={"application_metadata": metadata_encoded},
            target_id=target_id,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.METADATA_TOO_LARGE,
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestTargetName:
    """
    Tests for the target name field.
    """

    _MAX_CHAR_VALUE = 65535
    _MAX_NAME_LENGTH = 64

    @staticmethod
    @pytest.mark.parametrize(
        "name",
        [
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
        """
        A target's name must be a string of length 0 < N < 65.

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
        name: str,
        target_id: str,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
        status_code: int,
        result_code: ResultCodes,
    ) -> None:
        """
        A target's name must be a string of length 0 < N < 65.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        response = update_target(
            vuforia_database=vuforia_database,
            data={"name": name},
            target_id=target_id,
        )

        assert_vws_failure(
            response=response,
            status_code=status_code,
            result_code=result_code,
        )

    @staticmethod
    def test_existing_target_name(
        image_file_success_state_low_rating: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
    ) -> None:
        """
        Only one target can have a given name.
        """
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

        response = update_target(
            vuforia_database=vuforia_database,
            data={"name": first_target_name},
            target_id=second_target_id,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.FORBIDDEN,
            result_code=ResultCodes.TARGET_NAME_EXIST,
        )

    @staticmethod
    def test_same_name_given(
        image_file_success_state_low_rating: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
    ) -> None:
        """
        Updating a target with its own name does not give an error.
        """
        name = "example"

        target_id = vws_client.add_target(
            name=name,
            width=1,
            image=image_file_success_state_low_rating,
            active_flag=True,
            application_metadata=None,
        )

        vws_client.wait_for_target_processed(target_id=target_id)

        response = update_target(
            vuforia_database=vuforia_database,
            data={"name": name},
            target_id=target_id,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.OK,
            result_code=ResultCodes.SUCCESS,
        )

        target_details = vws_client.get_target_record(target_id=target_id)
        assert target_details.target_record.name == name


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestImage:
    """
    Tests for the image parameter.

    The specification for images is documented at
    https://library.vuforia.com/features/images/image-targets.html.
    """

    @staticmethod
    def test_image_valid(
        vuforia_database: VuforiaDatabase,
        image_files_failed_state: io.BytesIO,
        target_id: str,
        vws_client: VWS,
    ) -> None:
        """
        JPEG and PNG files in the RGB and greyscale color spaces are allowed.
        """
        image_file = image_files_failed_state
        image_data = image_file.read()
        image_data_encoded = base64.b64encode(image_data).decode("ascii")

        vws_client.wait_for_target_processed(target_id=target_id)

        response = update_target(
            vuforia_database=vuforia_database,
            data={"image": image_data_encoded},
            target_id=target_id,
        )

        assert_vws_response(
            response=response,
            status_code=HTTPStatus.OK,
            result_code=ResultCodes.SUCCESS,
        )

    @staticmethod
    def test_bad_image_format_or_color_space(
        bad_image_file: io.BytesIO,
        target_id: str,
        vws_client: VWS,
    ) -> None:
        """
        A `BAD_IMAGE` response is returned if an image which is not a JPEG
        or PNG file is given, or if the given image is not in the greyscale or
        RGB color space.
        """
        vws_client.wait_for_target_processed(target_id=target_id)
        with pytest.raises(BadImage) as exc:
            vws_client.update_target(target_id=target_id, image=bad_image_file)

        status_code = exc.value.response.status_code
        assert status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    @staticmethod
    def test_corrupted(
        vws_client: VWS,
        corrupted_image_file: io.BytesIO,
        target_id: str,
    ) -> None:
        """
        No error is returned when the given image is corrupted.
        """
        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.update_target(
            target_id=target_id,
            image=corrupted_image_file,
        )

    @staticmethod
    def test_image_too_large(
        vuforia_database: VuforiaDatabase,
        target_id: str,
        vws_client: VWS,
    ) -> None:
        """
        An `ImageTooLarge` result is returned if the image is above a certain
        threshold.
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

        image_data = png_not_too_large.read()
        image_data_encoded = base64.b64encode(image_data).decode("ascii")
        image_content_size = len(image_data)
        # We check that the image we created is just slightly smaller than the
        # maximum file size.
        #
        # This is just because of the implementation details of
        # ``max_image_file``.
        assert image_content_size < max_bytes
        assert (image_content_size * 1.05) > max_bytes

        response = update_target(
            vuforia_database=vuforia_database,
            data={"image": image_data_encoded},
            target_id=target_id,
        )

        assert_vws_response(
            response=response,
            status_code=HTTPStatus.OK,
            result_code=ResultCodes.SUCCESS,
        )

        vws_client.wait_for_target_processed(target_id=target_id)

        width = width + 1
        height = height + 1
        png_too_large = make_image_file(
            file_format="PNG",
            color_space="RGB",
            width=width,
            height=height,
        )

        image_data = png_too_large.read()
        image_data_encoded = base64.b64encode(image_data).decode("ascii")
        image_content_size = len(image_data)
        # We check that the image we created is just slightly smaller than the
        # maximum file size.
        #
        # This is just because of the implementation details of
        # ``max_image_file``.
        assert image_content_size < max_bytes
        assert (image_content_size * 1.05) > max_bytes

        response = update_target(
            vuforia_database=vuforia_database,
            data={"image": image_data_encoded},
            target_id=target_id,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.IMAGE_TOO_LARGE,
        )

    @staticmethod
    def test_not_base64_encoded_processable(
        vuforia_database: VuforiaDatabase,
        target_id: str,
        not_base64_encoded_processable: str,
        vws_client: VWS,
    ) -> None:
        """
        Some strings which are not valid base64 encoded strings are allowed as
        an image without getting a "Fail" response.
        This is because Vuforia treats them as valid base64, but then not a
        valid image.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        response = update_target(
            vuforia_database=vuforia_database,
            data={"image": not_base64_encoded_processable},
            target_id=target_id,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.BAD_IMAGE,
        )

    @staticmethod
    def test_not_base64_encoded_not_processable(
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
        target_id: str,
        not_base64_encoded_not_processable: str,
    ) -> None:
        """
        Some strings which are not valid base64 encoded strings are not
        processable by Vuforia, and then when given as an image Vuforia returns
        a "Fail" response.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        response = update_target(
            vuforia_database=vuforia_database,
            data={"image": not_base64_encoded_not_processable},
            target_id=target_id,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.FAIL,
        )

    @staticmethod
    def test_not_image(
        vuforia_database: VuforiaDatabase,
        target_id: str,
        vws_client: VWS,
    ) -> None:
        """
        If the given image is not an image file then a `BadImage` result is
        returned.
        """
        not_image_data = b"not_image_data"
        image_data_encoded = base64.b64encode(not_image_data).decode("ascii")

        vws_client.wait_for_target_processed(target_id=target_id)

        response = update_target(
            vuforia_database=vuforia_database,
            data={"image": image_data_encoded},
            target_id=target_id,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.BAD_IMAGE,
        )

    @staticmethod
    @pytest.mark.parametrize("invalid_type_image", [1, None])
    def test_invalid_type(
        invalid_type_image: int | None,
        target_id: str,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
    ) -> None:
        """
        If the given image is not a string, a `Fail` result is returned.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        response = update_target(
            vuforia_database=vuforia_database,
            data={"image": invalid_type_image},
            target_id=target_id,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )

    @staticmethod
    def test_rating_can_change(
        image_file_success_state_low_rating: io.BytesIO,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
    ) -> None:
        """
        If the target is updated with an image of different quality, the
        tracking rating can change.

        "quality" refers to Vuforia's internal rating system.
        The mock randomly assigns a quality and makes sure that the new quality
        is different to the old quality.
        """
        good_image = high_quality_image.read()
        good_image_data_encoded = base64.b64encode(good_image).decode("ascii")

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

        update_target(
            vuforia_database=vuforia_database,
            data={"image": good_image_data_encoded},
            target_id=target_id,
        )

        vws_client.wait_for_target_processed(target_id=target_id)
        target_details = vws_client.get_target_record(target_id=target_id)
        assert target_details.status == TargetStatuses.SUCCESS
        # Tracking rating is between 0 and 5 when status is 'success'
        new_tracking_rating = target_details.target_record.tracking_rating
        assert new_tracking_rating in range(6)

        assert original_tracking_rating != new_tracking_rating


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestInactiveProject:
    """
    Tests for inactive projects.
    """

    @staticmethod
    def test_inactive_project(inactive_vws_client: VWS) -> None:
        """
        If the project is inactive, a FORBIDDEN response is returned.
        """
        with pytest.raises(ProjectInactive):
            inactive_vws_client.update_target(target_id=uuid.uuid4().hex)
