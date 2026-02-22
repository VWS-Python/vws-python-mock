"""Tests for the `Authorization` header."""

import io
import json
import uuid
from http import HTTPStatus
from urllib.parse import urlparse

import pytest
from vws import VWS, CloudRecoService
from vws.exceptions import cloud_reco_exceptions
from vws.exceptions.vws_exceptions import AuthenticationFailureError, FailError
from vws_auth_tools import rfc_1123_date

from mock_vws._constants import ResultCodes
from mock_vws.database import CloudDatabase
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import (
    assert_valid_transaction_id,
    assert_vwq_failure,
    assert_vws_failure,
)
from tests.mock_vws.utils.too_many_requests import handle_server_errors


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestAuthorizationHeader:
    """
    Tests for what happens when the `Authorization` header is not as
    expected.
    """

    @staticmethod
    def test_missing(endpoint: Endpoint) -> None:
        """
        An `UNAUTHORIZED` response is returned when no `Authorization`
        header
        is given.
        """
        date = rfc_1123_date()
        new_headers = {
            **endpoint.headers,
            "Date": date,
        }
        new_headers.pop("Authorization", None)

        new_endpoint = Endpoint(
            base_url=endpoint.base_url,
            path_url=endpoint.path_url,
            method=endpoint.method,
            headers=new_headers,
            data=endpoint.data,
            successful_headers_result_code=endpoint.successful_headers_result_code,
            successful_headers_status_code=endpoint.successful_headers_status_code,
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
        )

        response = new_endpoint.send()

        handle_server_errors(response=response)

        netloc = urlparse(url=endpoint.base_url).netloc
        if netloc == "cloudreco.vuforia.com":
            assert_vwq_failure(
                response=response,
                status_code=HTTPStatus.UNAUTHORIZED,
                content_type="text/plain;charset=iso-8859-1",
                cache_control=None,
                www_authenticate="KWS",
                connection="keep-alive",
            )
            assert response.text == "Authorization header missing."
            return

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            result_code=ResultCodes.AUTHENTICATION_FAILURE,
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestMalformed:
    """Tests for passing a malformed ``Authorization`` header."""

    @staticmethod
    def test_one_part_no_space(endpoint: Endpoint) -> None:
        """A valid authorization string is two "parts" when split on a
        space.

        When
        a string is given which is one "part", a ``BAD_REQUEST`` or
        ``UNAUTHORIZED`` response is returned.
        """
        date = rfc_1123_date()

        # We use "VWS" as this is the first part of a valid authorization
        # string, but really any string which is not two parts when split on a
        # space will do.
        authorization_string = "VWS"
        new_headers = {
            **endpoint.headers,
            "Authorization": authorization_string,
            "Date": date,
        }

        new_endpoint = Endpoint(
            base_url=endpoint.base_url,
            path_url=endpoint.path_url,
            method=endpoint.method,
            headers=new_headers,
            data=endpoint.data,
            successful_headers_result_code=endpoint.successful_headers_result_code,
            successful_headers_status_code=endpoint.successful_headers_status_code,
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
        )

        response = new_endpoint.send()
        handle_server_errors(response=response)

        netloc = urlparse(url=endpoint.base_url).netloc
        if netloc == "cloudreco.vuforia.com":
            assert_vwq_failure(
                response=response,
                status_code=HTTPStatus.UNAUTHORIZED,
                content_type="text/plain;charset=iso-8859-1",
                cache_control=None,
                www_authenticate="KWS",
                connection="keep-alive",
            )
            assert response.text == "Malformed authorization header."
            return

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )

    @staticmethod
    def test_one_part_with_space(endpoint: Endpoint) -> None:
        """A valid authorization string is two "parts" when split on a
        space.

        When
        a string is given which is one "part", a ``BAD_REQUEST`` or
        ``UNAUTHORIZED`` response is returned.
        """
        authorization_string = "VWS "
        date = rfc_1123_date()
        new_headers = {
            **endpoint.headers,
            "Authorization": authorization_string,
            "Date": date,
        }

        new_endpoint = Endpoint(
            base_url=endpoint.base_url,
            path_url=endpoint.path_url,
            method=endpoint.method,
            headers=new_headers,
            data=endpoint.data,
            successful_headers_result_code=endpoint.successful_headers_result_code,
            successful_headers_status_code=endpoint.successful_headers_status_code,
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
        )

        response = new_endpoint.send()
        handle_server_errors(response=response)

        netloc = urlparse(url=endpoint.base_url).netloc
        if netloc == "cloudreco.vuforia.com":
            assert_vwq_failure(
                response=response,
                status_code=HTTPStatus.UNAUTHORIZED,
                content_type="text/plain;charset=iso-8859-1",
                cache_control=None,
                www_authenticate="KWS",
                connection="keep-alive",
            )
            assert response.text == "Malformed authorization header."
            return

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )

    @staticmethod
    def test_missing_signature(endpoint: Endpoint) -> None:
        """
        If a signature is missing `Authorization` header is given, a
        ``BAD_REQUEST`` response is given.
        """
        date = rfc_1123_date()

        authorization_string = "VWS foobar:"
        new_headers = {
            **endpoint.headers,
            "Authorization": authorization_string,
            "Date": date,
        }

        new_endpoint = Endpoint(
            base_url=endpoint.base_url,
            path_url=endpoint.path_url,
            method=endpoint.method,
            headers=new_headers,
            data=endpoint.data,
            successful_headers_result_code=endpoint.successful_headers_result_code,
            successful_headers_status_code=endpoint.successful_headers_status_code,
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
        )

        response = new_endpoint.send()
        handle_server_errors(response=response)

        netloc = urlparse(url=endpoint.base_url).netloc
        if netloc == "cloudreco.vuforia.com":
            assert_vwq_failure(
                response=response,
                status_code=HTTPStatus.UNAUTHORIZED,
                content_type="text/plain;charset=iso-8859-1",
                cache_control=None,
                www_authenticate="KWS",
                connection="keep-alive",
            )
            assert response.text == "Malformed authorization header."
            return

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestBadKey:
    """Tests for making requests with incorrect keys."""

    @staticmethod
    def test_bad_access_key_services(
        vuforia_database: CloudDatabase,
    ) -> None:
        """
        If the server access key given does not match any database, a
        ``Fail``
        response is returned.
        """
        vws_client = VWS(
            server_access_key="example",
            server_secret_key=vuforia_database.server_secret_key,
        )

        with pytest.raises(expected_exception=FailError) as exc:
            vws_client.get_target_record(target_id=uuid.uuid4().hex)

        assert exc.value.response.status_code == HTTPStatus.BAD_REQUEST

    @staticmethod
    def test_bad_access_key_query(
        *,
        vuforia_database: CloudDatabase,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        If the client access key given is incorrect, an ``UNAUTHORIZED``
        response is returned.
        """
        cloud_reco_client = CloudRecoService(
            client_access_key="example",
            client_secret_key=vuforia_database.client_secret_key,
        )

        with pytest.raises(
            expected_exception=cloud_reco_exceptions.AuthenticationFailureError
        ) as exc:
            cloud_reco_client.query(image=high_quality_image)

        response = exc.value.response

        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            content_type="application/json",
            cache_control=None,
            www_authenticate="VWS",
            connection="keep-alive",
        )

        assert json.loads(s=response.text).keys() == {
            "transaction_id",
            "result_code",
        }
        assert_valid_transaction_id(response=response)
        result_code = json.loads(s=response.text)["result_code"]
        transaction_id = json.loads(s=response.text)["transaction_id"]
        assert result_code == ResultCodes.AUTHENTICATION_FAILURE.value
        # The separators are inconsistent and we test this.
        expected_text = (
            '{"transaction_id":'
            f'"{transaction_id}",'
            f'"result_code":"{result_code}"'
            "}"
        )
        assert response.text == expected_text

    @staticmethod
    def test_bad_secret_key_services(
        vuforia_database: CloudDatabase,
    ) -> None:
        """
        If the server secret key given is incorrect, an
        ``AuthenticationFailureError`` response is returned.
        """
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key="example",
        )

        with pytest.raises(expected_exception=AuthenticationFailureError):
            vws_client.get_target_record(target_id=uuid.uuid4().hex)

    @staticmethod
    def test_bad_secret_key_query(
        *,
        vuforia_database: CloudDatabase,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        If the client secret key given is incorrect, an ``UNAUTHORIZED``
        response is returned.
        """
        cloud_reco_client = CloudRecoService(
            client_access_key=vuforia_database.client_access_key,
            client_secret_key="example",
        )

        with pytest.raises(
            expected_exception=cloud_reco_exceptions.AuthenticationFailureError
        ) as exc:
            cloud_reco_client.query(image=high_quality_image)

        response = exc.value.response

        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            content_type="application/json",
            cache_control=None,
            www_authenticate="VWS",
            connection="keep-alive",
        )

        assert json.loads(s=response.text).keys() == {
            "transaction_id",
            "result_code",
        }
        assert_valid_transaction_id(response=response)
        result_code = json.loads(s=response.text)["result_code"]
        transaction_id = json.loads(s=response.text)["transaction_id"]
        assert result_code == ResultCodes.AUTHENTICATION_FAILURE.value
        # The separators are inconsistent and we test this.
        expected_text = (
            '{"transaction_id":'
            f'"{transaction_id}",'
            f'"result_code":"{result_code}"'
            "}"
        )
        assert response.text == expected_text
