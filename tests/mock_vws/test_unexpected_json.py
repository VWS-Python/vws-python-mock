"""Tests for giving JSON data to endpoints which do not expect it."""

import json
from http import HTTPStatus
from urllib.parse import urlparse

import pytest
from vws_auth_tools import authorization_header, rfc_1123_date

from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import assert_vwq_failure
from tests.mock_vws.utils.too_many_requests import handle_server_errors


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestUnexpectedJSON:
    """Tests for giving JSON to endpoints which do not expect it."""

    @staticmethod
    def test_does_not_take_data(endpoint: Endpoint) -> None:
        """
        Giving JSON to endpoints which do not take any JSON data returns
        error
        responses.
        """
        if (
            endpoint.headers.get(
                "Content-Type",
            )
            == "application/json"
        ):
            return
        content = json.dumps(obj={"key": "value"}).encode(encoding="utf-8")
        content_type = "application/json"
        date = rfc_1123_date()

        authorization_string = authorization_header(
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
            method=endpoint.method,
            content=content,
            content_type=content_type,
            date=date,
            request_path=endpoint.path_url,
        )

        new_headers = {
            **endpoint.headers,
            "Authorization": authorization_string,
            "Date": date,
            "Content-Type": content_type,
            "Content-Length": str(object=len(content)),
        }

        new_endpoint = Endpoint(
            base_url=endpoint.base_url,
            path_url=endpoint.path_url,
            method=endpoint.method,
            headers=new_headers,
            data=content,
            successful_headers_result_code=endpoint.successful_headers_result_code,
            successful_headers_status_code=endpoint.successful_headers_status_code,
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
        )

        response = new_endpoint.send()

        handle_server_errors(response=response)

        netloc = urlparse(url=endpoint.base_url).netloc
        if netloc == "cloudreco.vuforia.com":
            # The multipart/formdata boundary is no longer in the given
            # content.
            assert not response.text
            assert_vwq_failure(
                response=response,
                status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                content_type=None,
                cache_control=None,
                www_authenticate=None,
                connection="keep-alive",
            )
            return

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert not response.text
        assert "Content-Type" not in response.headers
