"""
Tests for the `Authorization` header.
"""
from __future__ import annotations

import json
import uuid
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
import requests
from mock_vws._constants import ResultCodes
from requests.structures import CaseInsensitiveDict
from vws import VWS, CloudRecoService
from vws.exceptions import cloud_reco_exceptions
from vws.exceptions.vws_exceptions import AuthenticationFailure, Fail
from vws_auth_tools import rfc_1123_date

from tests.mock_vws.utils.assertions import (
    assert_valid_date_header,
    assert_valid_transaction_id,
    assert_vwq_failure,
    assert_vws_failure,
)
from tests.mock_vws.utils.too_many_requests import handle_server_errors

if TYPE_CHECKING:
    import io

    from mock_vws.database import VuforiaDatabase

    from tests.mock_vws.utils import Endpoint


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestAuthorizationHeader:
    """
    Tests for what happens when the `Authorization` header is not as expected.
    """

    @staticmethod
    def test_missing(endpoint: Endpoint) -> None:
        """
        An `UNAUTHORIZED` response is returned when no `Authorization` header
        is given.
        """
        date = rfc_1123_date()
        headers: dict[str, str] = dict(endpoint.prepared_request.headers) | {
            "Date": date,
        }

        headers.pop("Authorization", None)

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)
        handle_server_errors(response=response)

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
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
    """
    Tests for passing a malformed ``Authorization`` header.
    """

    @staticmethod
    @pytest.mark.parametrize(
        "authorization_string",
        ["gibberish", "VWS"],
    )
    def test_one_part_no_space(
        endpoint: Endpoint,
        authorization_string: str,
    ) -> None:
        """
        A valid authorization string is two "parts" when split on a space. When
        a string is given which is one "part", a ``BAD_REQUEST`` or
        ``UNAUTHORIZED`` response is returned.
        """
        date = rfc_1123_date()

        headers: dict[str, str] = dict(endpoint.prepared_request.headers) | {
            "Authorization": authorization_string,
            "Date": date,
        }

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)
        handle_server_errors(response=response)

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
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
        """
        A valid authorization string is two "parts" when split on a space. When
        a string is given which is one "part", a ``BAD_REQUEST`` or
        ``UNAUTHORIZED`` response is returned.
        """
        authorization_string = "VWS "
        date = rfc_1123_date()

        headers: dict[str, str] = dict(endpoint.prepared_request.headers) | {
            "Authorization": authorization_string,
            "Date": date,
        }

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)
        handle_server_errors(response=response)

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
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
    @pytest.mark.parametrize(
        "authorization_string",
        [
            "VWS foobar:",
            "VWS foobar",
        ],
    )
    def test_missing_signature(
        endpoint: Endpoint,
        authorization_string: str,
    ) -> None:
        """
        If a signature is missing `Authorization` header is given, a
        ``BAD_REQUEST`` response is given.
        """
        date = rfc_1123_date()

        headers: dict[str, str] = dict(endpoint.prepared_request.headers) | {
            "Authorization": authorization_string,
            "Date": date,
        }

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)
        handle_server_errors(response=response)

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
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
    """
    Tests for making requests with incorrect keys.
    """

    @staticmethod
    def test_bad_access_key_services(
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        If the server access key given does not match any database, a ``Fail``
        response is returned.
        """
        vws_client = VWS(
            server_access_key="example",
            server_secret_key=vuforia_database.server_secret_key,
        )

        with pytest.raises(Fail) as exc:
            vws_client.get_target_record(target_id=uuid.uuid4().hex)

        assert exc.value.response.status_code == HTTPStatus.BAD_REQUEST

    @staticmethod
    def test_bad_access_key_query(
        vuforia_database: VuforiaDatabase,
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

        with pytest.raises(cloud_reco_exceptions.AuthenticationFailure) as exc:
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

        assert json.loads(response.text).keys() == {
            "transaction_id",
            "result_code",
        }
        assert_valid_transaction_id(response=response)
        assert_valid_date_header(response=response)
        result_code = json.loads(response.text)["result_code"]
        transaction_id = json.loads(response.text)["transaction_id"]
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
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        If the server secret key given is incorrect, an
        ``AuthenticationFailure`` response is returned.
        """
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key="example",
        )

        with pytest.raises(AuthenticationFailure):
            vws_client.get_target_record(target_id=uuid.uuid4().hex)

    @staticmethod
    def test_bad_secret_key_query(
        vuforia_database: VuforiaDatabase,
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

        with pytest.raises(cloud_reco_exceptions.AuthenticationFailure) as exc:
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

        assert json.loads(response.text).keys() == {
            "transaction_id",
            "result_code",
        }
        assert_valid_transaction_id(response=response)
        assert_valid_date_header(response=response)
        result_code = json.loads(response.text)["result_code"]
        transaction_id = json.loads(response.text)["transaction_id"]
        assert result_code == ResultCodes.AUTHENTICATION_FAILURE.value
        # The separators are inconsistent and we test this.
        expected_text = (
            '{"transaction_id":'
            f'"{transaction_id}",'
            f'"result_code":"{result_code}"'
            "}"
        )
        assert response.text == expected_text
