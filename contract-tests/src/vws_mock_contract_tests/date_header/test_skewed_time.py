"""
Tests for what happens when the `Date` header is given with an
unexpected
time.
"""

import json
from datetime import datetime
from http import HTTPStatus
from zoneinfo import ZoneInfo

from freezegun import freeze_time
from vws_auth_tools import authorization_header, rfc_1123_date

from vws_mock_contract_tests.date_header.helpers import (
    LEEWAY,
    VWQ_MAX_TIME_SKEW,
    VWS_MAX_TIME_SKEW,
)
from vws_mock_contract_tests.utils import Endpoint
from vws_mock_contract_tests.utils.assertions import (
    assert_query_success,
    assert_valid_transaction_id,
    assert_vwq_failure,
    assert_vws_failure,
    assert_vws_response,
)
from vws_mock_contract_tests.utils.too_many_requests import (
    handle_server_errors,
)


def test_date_out_of_range_after(
    endpoint: Endpoint, base_vwq_url: str
) -> None:
    """If the date header is more than five minutes (target API) or 65
    minutes (query API) after the request is sent, a `FORBIDDEN`
    response
    is returned.

    Because there is a small delay in sending requests and Vuforia
    isn't consistent, some leeway is given.
    """
    skew = (
        VWQ_MAX_TIME_SKEW
        if endpoint.base_url == base_vwq_url
        else VWS_MAX_TIME_SKEW
    )
    time_difference_from_now = skew + LEEWAY
    gmt = ZoneInfo(key="GMT")
    with freeze_time(
        time_to_freeze=datetime.now(tz=gmt) + time_difference_from_now
    ):
        date = rfc_1123_date()

    authorization_string = authorization_header(
        access_key=endpoint.access_key,
        secret_key=endpoint.secret_key,
        method=endpoint.method,
        content=endpoint.data,
        content_type=endpoint.auth_header_content_type,
        date=date,
        request_path=endpoint.path_url,
    )

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

    # Even with the query endpoint, we get a JSON response.
    if endpoint.base_url == base_vwq_url:
        response_json = json.loads(s=response.text)
        assert isinstance(response_json, dict)
        assert response_json.keys() == {"transaction_id", "result_code"}
        assert response_json["result_code"] == "RequestTimeTooSkewed"
        assert_valid_transaction_id(response=response)
        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.FORBIDDEN,
            content_type="application/json",
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )
        return

    assert_vws_failure(
        response=response,
        status_code=HTTPStatus.FORBIDDEN,
        result_code="RequestTimeTooSkewed",
    )


def test_date_out_of_range_before(
    endpoint: Endpoint, base_vwq_url: str
) -> None:
    """If the date header is more than five minutes (target API) or 65
    minutes (query API) before the request is sent, a `FORBIDDEN`
    response
    is returned.

    Because there is a small delay in sending requests and Vuforia
    isn't consistent, some leeway is given.
    """
    skew = (
        VWQ_MAX_TIME_SKEW
        if endpoint.base_url == base_vwq_url
        else VWS_MAX_TIME_SKEW
    )
    time_difference_from_now = skew + LEEWAY
    gmt = ZoneInfo(key="GMT")
    with freeze_time(
        time_to_freeze=datetime.now(tz=gmt) - time_difference_from_now
    ):
        date = rfc_1123_date()

    authorization_string = authorization_header(
        access_key=endpoint.access_key,
        secret_key=endpoint.secret_key,
        method=endpoint.method,
        content=endpoint.data,
        content_type=endpoint.auth_header_content_type,
        date=date,
        request_path=endpoint.path_url,
    )

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

    # Even with the query endpoint, we get a JSON response.
    if endpoint.base_url == base_vwq_url:
        response_json = json.loads(s=response.text)
        assert isinstance(response_json, dict)
        assert response_json.keys() == {"transaction_id", "result_code"}
        assert response_json["result_code"] == "RequestTimeTooSkewed"
        assert_valid_transaction_id(response=response)
        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.FORBIDDEN,
            content_type="application/json",
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )
        return

    assert_vws_failure(
        response=response,
        status_code=HTTPStatus.FORBIDDEN,
        result_code="RequestTimeTooSkewed",
    )


def test_date_in_range_after(endpoint: Endpoint, base_vwq_url: str) -> None:
    """If a date header is within five minutes after the request is
    sent,
    no error is returned.

    Because there is a small delay in sending requests and Vuforia
    isn't consistent, some leeway is given.
    """
    skew = (
        VWQ_MAX_TIME_SKEW
        if endpoint.base_url == base_vwq_url
        else VWS_MAX_TIME_SKEW
    )
    time_difference_from_now = skew - LEEWAY
    gmt = ZoneInfo(key="GMT")
    with freeze_time(
        time_to_freeze=datetime.now(tz=gmt) + time_difference_from_now
    ):
        date = rfc_1123_date()

    authorization_string = authorization_header(
        access_key=endpoint.access_key,
        secret_key=endpoint.secret_key,
        method=endpoint.method,
        content=endpoint.data,
        content_type=endpoint.auth_header_content_type,
        date=date,
        request_path=endpoint.path_url,
    )

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

    if endpoint.base_url == base_vwq_url:
        assert_query_success(response=response)
        return

    if endpoint.successful_headers_result_code is None:
        assert response.status_code == endpoint.successful_headers_status_code
        return

    assert_vws_response(
        response=response,
        status_code=endpoint.successful_headers_status_code,
        result_code=endpoint.successful_headers_result_code,
    )


def test_date_in_range_before(endpoint: Endpoint, base_vwq_url: str) -> None:
    """If a date header is within five minutes before the request is
    sent,
    no error is returned.

    Because there is a small delay in sending requests and Vuforia
    isn't consistent, some leeway is given.
    """
    skew = (
        VWQ_MAX_TIME_SKEW
        if endpoint.base_url == base_vwq_url
        else VWS_MAX_TIME_SKEW
    )
    time_difference_from_now = skew - LEEWAY
    gmt = ZoneInfo(key="GMT")
    with freeze_time(
        time_to_freeze=datetime.now(tz=gmt) - time_difference_from_now
    ):
        date = rfc_1123_date()

    authorization_string = authorization_header(
        access_key=endpoint.access_key,
        secret_key=endpoint.secret_key,
        method=endpoint.method,
        content=endpoint.data,
        content_type=endpoint.auth_header_content_type,
        date=date,
        request_path=endpoint.path_url,
    )

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

    if endpoint.base_url == base_vwq_url:
        assert_query_success(response=response)
        return

    if endpoint.successful_headers_result_code is None:
        assert response.status_code == endpoint.successful_headers_status_code
        return

    assert_vws_response(
        response=response,
        status_code=endpoint.successful_headers_status_code,
        result_code=endpoint.successful_headers_result_code,
    )
