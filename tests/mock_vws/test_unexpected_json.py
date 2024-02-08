"""
Tests for giving JSON data to endpoints which do not expect it.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
import requests
from requests.structures import CaseInsensitiveDict
from vws_auth_tools import authorization_header, rfc_1123_date

from tests.mock_vws.utils.assertions import assert_vwq_failure
from tests.mock_vws.utils.too_many_requests import handle_server_errors

if TYPE_CHECKING:
    from tests.mock_vws.utils import Endpoint


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestUnexpectedJSON:
    """
    Tests for giving JSON to endpoints which do not expect it.
    """

    @staticmethod
    def test_does_not_take_data(endpoint: Endpoint) -> None:
        """
        Giving JSON to endpoints which do not take any JSON data returns error
        responses.
        """
        if (
            endpoint.prepared_request.headers.get(
                "Content-Type",
            )
            == "application/json"
        ):
            return
        content = bytes(json.dumps({"key": "value"}), encoding="utf-8")
        content_type = "application/json"
        date = rfc_1123_date()

        endpoint_headers = dict(endpoint.prepared_request.headers)

        authorization_string = authorization_header(
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
            method=str(endpoint.prepared_request.method),
            content=content,
            content_type=content_type,
            date=date,
            request_path=endpoint.prepared_request.path_url,
        )

        headers = endpoint_headers | {
            "Authorization": authorization_string,
            "Date": date,
            "Content-Type": content_type,
        }

        endpoint.prepared_request.body = content
        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        endpoint.prepared_request.prepare_content_length(body=content)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)
        handle_server_errors(response=response)

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
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
