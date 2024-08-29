"""
Tests for the mock of the add target endpoint.
"""

import base64
import io
import json
from http import HTTPMethod, HTTPStatus
from string import hexdigits
from typing import Any, Final
from urllib.parse import urljoin

import pytest
import requests
from beartype import beartype
from dirty_equals import IsInstance
from requests.structures import CaseInsensitiveDict
from vws import VWS
from vws.exceptions.custom_exceptions import OopsAnErrorOccurredPossiblyBadName
from vws.exceptions.response import Response
from vws.exceptions.vws_exceptions import (
    BadImage,
    Fail,
    ImageTooLarge,
    MetadataTooLarge,
    ProjectInactive,
    TargetNameExist,
)
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws._constants import ResultCodes
from mock_vws.database import VuforiaDatabase
from tests.mock_vws.utils import make_image_file
from tests.mock_vws.utils.assertions import (
    assert_valid_date_header,
    assert_vws_failure,
    assert_vws_response,
)
from tests.mock_vws.utils.too_many_requests import handle_server_errors

_MAX_METADATA_BYTES: Final[int] = 1024 * 1024 - 1


@beartype
def _add_target_to_vws(
    *,
    vuforia_database: VuforiaDatabase,
    data: dict[str, Any],
    content_type: str = "application/json",
) -> requests.Response:
    """
    Return a response from a request to the endpoint to add a target.

    Args:
        vuforia_database: The credentials to use to connect to Vuforia.
        data: The data to send, in JSON format, to the endpoint.
        content_type: The `Content-Type` header to use.

    Returns:
        The response returned by the API.
    """
    date = rfc_1123_date()
    request_path = "/targets"

    content = json.dumps(obj=data).encode(encoding="utf-8")

    authorization_string = authorization_header(
        access_key=vuforia_database.server_access_key,
        secret_key=vuforia_database.server_secret_key,
        method=HTTPMethod.POST,
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

    response = requests.request(
        method=HTTPMethod.POST,
        url=urljoin(base="https://vws.vuforia.com/", url=request_path),
        headers=headers,
        data=content,
        timeout=30,
    )

    handle_server_errors(response=response)
    return response


@beartype
def _assert_oops_response(response: Response) -> None:
    """
    Assert that the response is in the format of Vuforia's "Oops, an error
    occurred" HTML response.

    Raises:
        AssertionError: The given response is not expected format.
    """
    assert_valid_date_header(response=response)
    assert "Oops, an error occurred" in response.text
    assert "This exception has been logged with id" in response.text

    expected_headers = CaseInsensitiveDict(
        data={
            "Connection": "keep-alive",
            "Content-Type": "text/html; charset=UTF-8",
            "Date": response.headers["Date"],
            "server": "envoy",
            "Content-Length": "1190",
            "x-envoy-upstream-service-time": IsInstance(expected_type=str),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": IsInstance(expected_type=str),
            "x-content-type-options": "nosniff",
        },
    )
    assert response.headers == expected_headers


def assert_success(response: requests.Response) -> None:
    """
    Assert that the given response is a success response for adding a
    target.

    Raises:
        AssertionError: The given response is not a valid success response
            for adding a target.
    """
    assert_vws_response(
        response=response,
        status_code=HTTPStatus.CREATED,
        result_code=ResultCodes.TARGET_CREATED,
    )
    expected_keys = {"result_code", "transaction_id", "target_id"}
    assert response.json().keys() == expected_keys
    target_id = response.json()["target_id"]
    expected_target_id_length = 32
    assert len(target_id) == expected_target_id_length
    assert all(char in hexdigits for char in target_id)


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestContentTypes:
    """
    Tests for the `Content-Type` header.
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
        ids=[
            "Documented Content-Type",
            "Undocumented Content-Type",
        ],
    )
    def test_content_types(
        vuforia_database: VuforiaDatabase,
        image_file_failed_state: io.BytesIO,
        content_type: str,
    ) -> None:
        """
        Any non-empty ``Content-Type`` header is allowed.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(s=image_data).decode("ascii")

        data = {
            "name": "example",
            "width": 1,
            "image": image_data_encoded,
        }

        response = _add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
            content_type=content_type,
        )

        assert_success(response=response)

    @staticmethod
    def test_empty_content_type(
        vuforia_database: VuforiaDatabase,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        An ``UNAUTHORIZED`` response is given if an empty ``Content-Type``
        header is given.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(s=image_data).decode("ascii")

        data = {
            "name": "example",
            "width": 1,
            "image": image_data_encoded,
        }

        response = _add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
            content_type="",
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            result_code=ResultCodes.AUTHENTICATION_FAILURE,
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestMissingData:
    """
    Tests for giving incomplete data.
    """

    @staticmethod
    @pytest.mark.parametrize("data_to_remove", ["name", "width", "image"])
    def test_missing_data(
        vuforia_database: VuforiaDatabase,
        image_file_failed_state: io.BytesIO,
        data_to_remove: str,
    ) -> None:
        """
        `name`, `width` and `image` are all required.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(s=image_data).decode("ascii")

        data = {
            "name": "example_name",
            "width": 1,
            "image": image_data_encoded,
        }
        data.pop(data_to_remove)

        response = _add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
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
        image_file_failed_state: io.BytesIO,
        width: int | str | None,
    ) -> None:
        """
        The width must be a number greater than zero.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(s=image_data).decode("ascii")

        data = {
            "name": "example_name",
            "width": width,
            "image": image_data_encoded,
        }

        response = _add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )

    @staticmethod
    def test_width_valid(
        vws_client: VWS,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        Positive numbers are valid widths.
        """
        vws_client.add_target(
            name="example",
            width=0.01,
            image=image_file_failed_state,
            application_metadata=None,
            active_flag=True,
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
        image_file_failed_state: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        Names between 1 and 64 characters in length are valid.
        """
        vws_client.add_target(
            name=name,
            width=1,
            image=image_file_failed_state,
            application_metadata=None,
            active_flag=True,
        )

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("name", "status_code"),
        argvalues=[
            (1, HTTPStatus.BAD_REQUEST),
            ("", HTTPStatus.BAD_REQUEST),
            ("a" * (_MAX_NAME_LENGTH + 1), HTTPStatus.BAD_REQUEST),
            (None, HTTPStatus.BAD_REQUEST),
            (chr(_MAX_CHAR_VALUE + 1), HTTPStatus.INTERNAL_SERVER_ERROR),
            (
                chr(_MAX_CHAR_VALUE + 1) * (_MAX_NAME_LENGTH + 1),
                HTTPStatus.BAD_REQUEST,
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
        image_file_failed_state: io.BytesIO,
        status_code: int,
        vws_client: VWS,
    ) -> None:
        """
        A target's name must be a string of length 0 < N < 65, with characters
        in a particular range.
        """
        if status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            with pytest.raises(
                expected_exception=OopsAnErrorOccurredPossiblyBadName,
            ) as oops_exc:
                vws_client.add_target(
                    name=name,  # type: ignore[arg-type]
                    width=1,
                    image=image_file_failed_state,
                    application_metadata=None,
                    active_flag=True,
                )
            assert oops_exc.value.response.status_code == status_code
            _assert_oops_response(response=oops_exc.value.response)
            return

        with pytest.raises(expected_exception=Fail) as exc:
            vws_client.add_target(
                name=name,  # type: ignore[arg-type]
                width=1,
                image=image_file_failed_state,
                application_metadata=None,
                active_flag=True,
            )
        assert_vws_failure(
            response=exc.value.response,
            status_code=status_code,
            result_code=ResultCodes.FAIL,
        )

    @staticmethod
    def test_existing_target_name(
        image_file_failed_state: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        Only one target can have a given name.
        """
        vws_client.add_target(
            name="example_name",
            width=1,
            image=image_file_failed_state,
            application_metadata=None,
            active_flag=True,
        )

        with pytest.raises(expected_exception=TargetNameExist) as exc:
            vws_client.add_target(
                name="example_name",
                width=1,
                image=image_file_failed_state,
                application_metadata=None,
                active_flag=True,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.FORBIDDEN,
            result_code=ResultCodes.TARGET_NAME_EXIST,
        )

    @staticmethod
    def test_deleted_existing_target_name(
        image_file_failed_state: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        A target can be added with the name of a deleted target.
        """
        target_id = vws_client.add_target(
            name="example_name",
            width=1,
            image=image_file_failed_state,
            application_metadata=None,
            active_flag=True,
        )

        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.delete_target(target_id=target_id)
        vws_client.add_target(
            name="example_name",
            width=1,
            image=image_file_failed_state,
            application_metadata=None,
            active_flag=True,
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestImage:
    """
    Tests for the image parameter.

    The specification for images is documented at
    https://library.vuforia.com/features/images/image-targets.html.
    """

    @staticmethod
    def test_image_valid(
        vws_client: VWS,
        image_files_failed_state: io.BytesIO,
    ) -> None:
        """
        JPEG and PNG files in the RGB and greyscale color spaces are allowed.
        """
        vws_client.add_target(
            name="example_name",
            width=1,
            image=image_files_failed_state,
            application_metadata=None,
            active_flag=True,
        )

    @staticmethod
    def test_bad_image_format_or_color_space(
        bad_image_file: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        An `UNPROCESSABLE_ENTITY` response is returned if an image which is not
        a JPEG or PNG file is given, or if the given image is not in the
        greyscale or RGB color space.
        """
        with pytest.raises(expected_exception=BadImage) as exc:
            vws_client.add_target(
                name="example_name",
                width=1,
                image=bad_image_file,
                application_metadata=None,
                active_flag=True,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.BAD_IMAGE,
        )

    @staticmethod
    def test_corrupted(
        corrupted_image_file: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        No error is returned when the given image is corrupted.
        """
        vws_client.add_target(
            name="example_name",
            width=1,
            image=corrupted_image_file,
            application_metadata=None,
            active_flag=True,
        )

    @staticmethod
    def test_image_file_size_too_large(vws_client: VWS) -> None:
        """
        An ``ImageTooLarge`` result is returned if the image file size is above
        a certain threshold.
        """
        max_bytes = 2.3 * 1024 * 1024
        width = height = 886
        png_not_too_large = make_image_file(
            file_format="PNG",
            color_space="RGB",
            width=width,
            height=height,
        )

        image_data = png_not_too_large.getvalue()
        image_content_size = len(image_data)
        # We check that the image we created is just slightly smaller than the
        # maximum file size.
        #
        # This is just because of the implementation details of
        # ``max_image_file``.
        assert image_content_size < max_bytes
        assert (image_content_size * 1.05) > max_bytes

        vws_client.add_target(
            name="example_name",
            width=1,
            image=png_not_too_large,
            application_metadata=None,
            active_flag=True,
        )

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

        with pytest.raises(expected_exception=ImageTooLarge) as exc:
            vws_client.add_target(
                name="example_name_2",
                width=1,
                image=png_too_large,
                application_metadata=None,
                active_flag=True,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.IMAGE_TOO_LARGE,
        )

    @staticmethod
    def test_not_base64_encoded_processable(
        vuforia_database: VuforiaDatabase,
        not_base64_encoded_processable: str,
    ) -> None:
        """
        Some strings which are not valid base64 encoded strings are allowed as
        an image without getting a "Fail" response.
        This is because Vuforia treats them as valid base64, but then not a
        valid image.
        """
        data = {
            "name": "example_name",
            "width": 1,
            "image": not_base64_encoded_processable,
        }

        response = _add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.BAD_IMAGE,
        )

    @staticmethod
    def test_not_base64_encoded_not_processable(
        vuforia_database: VuforiaDatabase,
        not_base64_encoded_not_processable: str,
    ) -> None:
        """
        Some strings which are not valid base64 encoded strings are not
        processable by Vuforia, and then when given as an image Vuforia returns
        a "Fail" response.
        """
        data = {
            "name": "example_name",
            "width": 1,
            "image": not_base64_encoded_not_processable,
        }

        response = _add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.FAIL,
        )

    @staticmethod
    def test_not_image(vws_client: VWS) -> None:
        """
        If the given image is not an image file then a `BadImage` result is
        returned.
        """
        with pytest.raises(expected_exception=BadImage) as exc:
            vws_client.add_target(
                name="example_name",
                width=1,
                image=io.BytesIO(initial_bytes=b"not_image_data"),
                application_metadata=None,
                active_flag=True,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.BAD_IMAGE,
        )

    @staticmethod
    @pytest.mark.parametrize("invalid_type_image", [1, None])
    def test_invalid_type(
        invalid_type_image: int | None,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        If the given image is not a string, a `Fail` result is returned.
        """
        data = {
            "name": "example_name",
            "width": 1,
            "image": invalid_type_image,
        }

        response = _add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestActiveFlag:
    """
    Tests for the active flag parameter.
    """

    @staticmethod
    @pytest.mark.parametrize("active_flag", [True, False, None])
    def test_valid(
        active_flag: bool | None,
        image_file_failed_state: io.BytesIO,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        Boolean values and NULL are valid active flags.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(s=image_data).decode("ascii")
        content_type = "application/json"

        data = {
            "name": "example",
            "width": 1,
            "image": image_data_encoded,
            "active_flag": active_flag,
        }

        response = _add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
            content_type=content_type,
        )

        assert_success(response=response)

    @staticmethod
    def test_invalid(
        image_file_failed_state: io.BytesIO,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        Values which are not Boolean values or NULL are not valid active flags.
        """
        active_flag = "string"
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(s=image_data).decode("ascii")
        content_type = "application/json"

        data = {
            "name": "example",
            "width": 1,
            "image": image_data_encoded,
            "active_flag": active_flag,
        }

        response = _add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
            content_type=content_type,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )

    @staticmethod
    def test_not_set(
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        The active flag defaults to True if it is not set.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(s=image_data).decode("ascii")

        data = {
            "name": "my_example_name",
            "width": 1234,
            "image": image_data_encoded,
        }

        response = _add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
        )

        target_id = response.json()["target_id"]
        target_details = vws_client.get_target_record(target_id=target_id)
        assert target_details.target_record.active_flag is True

    @staticmethod
    def test_set_to_none(
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        The active flag defaults to True if it is set to NULL.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(s=image_data).decode("ascii")

        data = {
            "name": "my_example_name",
            "width": 1234,
            "image": image_data_encoded,
            "active_flag": None,
        }

        response = _add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
        )

        target_id = response.json()["target_id"]
        target_details = vws_client.get_target_record(target_id=target_id)
        assert target_details.target_record.active_flag is True


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestUnexpectedData:
    """
    Tests for passing data which is not mandatory or allowed to the endpoint.
    """

    @staticmethod
    def test_invalid_extra_data(
        vuforia_database: VuforiaDatabase,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        A `BAD_REQUEST` response is returned when unexpected data is given.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(s=image_data).decode("ascii")

        data = {
            "name": "example_name",
            "width": 1,
            "image": image_data_encoded,
            "extra_thing": 1,
        }

        response = _add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
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
        image_file_failed_state: io.BytesIO,
        metadata: bytes,
        vws_client: VWS,
    ) -> None:
        """
        A base64 encoded string is valid application metadata.
        """
        metadata_encoded = base64.b64encode(s=metadata).decode("ascii")

        vws_client.add_target(
            name="example",
            width=1,
            image=image_file_failed_state,
            application_metadata=metadata_encoded,
            active_flag=True,
        )

    @staticmethod
    def test_null(
        vuforia_database: VuforiaDatabase,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        NULL is valid application metadata.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(s=image_data).decode("ascii")

        request_data = {
            "name": "example_name",
            "width": 1,
            "image": image_data_encoded,
            "application_metadata": None,
        }

        response = _add_target_to_vws(
            vuforia_database=vuforia_database,
            data=request_data,
        )

        assert_success(response=response)

    @staticmethod
    def test_invalid_type(
        vuforia_database: VuforiaDatabase,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        Values which are not a string or NULL are not valid application
        metadata.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(s=image_data).decode("ascii")

        data = {
            "name": "example_name",
            "width": 1,
            "image": image_data_encoded,
            "application_metadata": 1,
        }

        response = _add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
        )

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )

    @staticmethod
    def test_not_base64_encoded_processable(
        high_quality_image: io.BytesIO,
        not_base64_encoded_processable: str,
        vws_client: VWS,
    ) -> None:
        """
        Some strings which are not valid base64 encoded strings are allowed as
        application metadata.
        """
        vws_client.add_target(
            name="example",
            width=1,
            image=high_quality_image,
            application_metadata=not_base64_encoded_processable,
            active_flag=True,
        )

    @staticmethod
    def test_not_base64_encoded_not_processable(
        high_quality_image: io.BytesIO,
        not_base64_encoded_not_processable: str,
        vws_client: VWS,
    ) -> None:
        """
        Some strings which are not valid base64 encoded strings are not allowed
        as application metadata.
        """
        with pytest.raises(expected_exception=Fail) as exc:
            vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                application_metadata=not_base64_encoded_not_processable,
                active_flag=True,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.FAIL,
        )

    @staticmethod
    def test_metadata_too_large(
        image_file_failed_state: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        A base64 encoded string of greater than 1024 * 1024 bytes is too large
        for application metadata.
        """
        metadata = b"a" * (_MAX_METADATA_BYTES + 1)
        metadata_encoded = base64.b64encode(s=metadata).decode("ascii")

        with pytest.raises(expected_exception=MetadataTooLarge) as exc:
            vws_client.add_target(
                name="example",
                width=1,
                image=image_file_failed_state,
                application_metadata=metadata_encoded,
                active_flag=True,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            result_code=ResultCodes.METADATA_TOO_LARGE,
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestInactiveProject:
    """
    Tests for inactive projects.
    """

    @staticmethod
    def test_inactive_project(
        image_file_failed_state: io.BytesIO,
        inactive_vws_client: VWS,
    ) -> None:
        """
        If the project is inactive, a FORBIDDEN response is returned.
        """
        with pytest.raises(expected_exception=ProjectInactive) as exc:
            inactive_vws_client.add_target(
                name="example",
                width=1,
                image=image_file_failed_state,
                application_metadata=None,
                active_flag=True,
            )

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.FORBIDDEN,
            result_code=ResultCodes.PROJECT_INACTIVE,
        )
