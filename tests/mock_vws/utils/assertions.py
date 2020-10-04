"""
Assertion helpers.
"""

import copy
import datetime
import email.utils
import json
from http import HTTPStatus
from string import hexdigits
from typing import Optional

from backports.zoneinfo import ZoneInfo
from requests import Response

from mock_vws._constants import ResultCodes


def assert_vws_failure(
    response: Response,
    status_code: int,
    result_code: ResultCodes,
) -> None:
    """
    Assert that a VWS failure response is as expected.

    Args:
        response: The response returned by a request to VWS.
        status_code: The expected status code of the response.
        result_code: The expected result code of the response.

    Raises:
        AssertionError: The response is not in the expected VWS error format
            for the given codes.
    """
    assert response.json().keys() == {'transaction_id', 'result_code'}
    assert_vws_response(
        response=response,
        status_code=status_code,
        result_code=result_code,
    )


def assert_valid_date_header(response: Response) -> None:
    """
    Assert that a response includes a `Date` header which is within two minutes
    of "now".

    Args:
        response: The response returned by a request to a Vuforia service.

    Raises:
        AssertionError: The response does not include a `Date` header which is
            within one minute of "now".
    """
    date_response = response.headers['Date']
    date_from_response = email.utils.parsedate(date_response)
    assert date_from_response is not None
    year, month, day, hour, minute, second, _, _, _ = date_from_response
    gmt = ZoneInfo('GMT')
    datetime_from_response = datetime.datetime(
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        second=second,
        tzinfo=gmt,
    )
    current_date = datetime.datetime.now(tz=gmt)
    time_difference = abs(current_date - datetime_from_response)
    assert time_difference < datetime.timedelta(minutes=2)


def assert_valid_transaction_id(response: Response) -> None:
    """
    Assert that a response includes a valid transaction ID.

    Args:
        response: The response returned by a request to a Vuforia service.

    Raises:
        AssertionError: The response does not include a valid transaction ID.
    """
    transaction_id = response.json()['transaction_id']
    assert len(transaction_id) == 32
    assert all(char in hexdigits for char in transaction_id)


def assert_json_separators(response: Response) -> None:
    """
    Assert that a JSON response is formatted correctly.

    Args:
        response: The response returned by a request to a Vuforia service.

    Raises:
        AssertionError: The response JSON is not formatted correctly.
    """
    assert response.text == json.dumps(
        obj=response.json(),
        separators=(',', ':'),
    )


def assert_vws_response(
    response: Response,
    status_code: int,
    result_code: ResultCodes,
) -> None:
    """
    Assert that a VWS response is as expected, at least in part.

    https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Interperete-VWS-API-Result-Codes
    implies that the expected status code can be worked out from the result
    code. However, this is not the case as the real results differ from the
    documentation.

    For example, it is possible to get a "Fail" result code and a 400 error.

    Args:
        response: The response returned by a request to VWS.
        status_code: The expected status code of the response.
        result_code: The expected result code of the response.

    Raises:
        AssertionError: The response is not in the expected VWS format for the
            given codes.
    """
    assert response.status_code == status_code
    response_result_code = response.json()['result_code']
    assert response_result_code == result_code.value
    response_header_keys = {
        'Connection',
        'Content-Length',
        'Content-Type',
        'Date',
        'Server',
    }
    assert response.headers.keys() == response_header_keys
    assert response.headers['Connection'] == 'keep-alive'
    assert response.headers['Content-Length'] == str(len(response.text))
    assert response.headers['Content-Type'] == 'application/json'
    assert response.headers['Server'] == 'nginx'
    assert_json_separators(response=response)
    assert_valid_transaction_id(response=response)
    assert_valid_date_header(response=response)


def assert_query_success(response: Response) -> None:
    """
    Assert that the given response is a success response for performing an
    image recognition query.

    Raises:
        AssertionError: The given response is not a valid success response
            for performing an image recognition query.
    """
    assert response.status_code == HTTPStatus.OK
    assert response.json().keys() == {'result_code', 'results', 'query_id'}

    query_id = response.json()['query_id']
    assert len(query_id) == 32
    assert all(char in hexdigits for char in query_id)

    assert response.json()['result_code'] == 'Success'
    assert_valid_date_header(response=response)
    copied_response_headers = dict(copy.deepcopy(response.headers))
    copied_response_headers.pop('Date')

    # In the mock, all responses have the ``Content-Encoding`` ``gzip``.
    # In the real Vuforia, some do and some do not.
    # We are not sure why.
    content_encoding = copied_response_headers.pop('Content-Encoding', None)
    assert content_encoding in (None, 'gzip')

    expected_response_header_not_chunked = {
        'Connection': 'keep-alive',
        'Content-Length': str(response.raw.tell()),
        'Content-Type': 'application/json',
        'Server': 'nginx',
    }

    # The mock does not send chunked responses.
    expected_response_header_chunked = {
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Server': 'nginx',
        'transfer-encoding': 'chunked',
    }

    assert copied_response_headers in (
        expected_response_header_chunked,
        expected_response_header_not_chunked,
    )


def assert_vwq_failure(
    response: Response,
    status_code: int,
    content_type: Optional[str],
    cache_control: Optional[str],
    www_authenticate: Optional[str],
) -> None:
    """
    Assert that a VWQ failure response is as expected.

    Args:
        response: The response returned by a request to VWQ.
        content_type: The expected Content-Type header.
        status_code: The expected status code.
        cache_control: The expected Cache-Control header.
        www_authenticate: The expected WWW-Authenticate header.

    Raises:
        AssertionError: The response is not in the expected VWQ error format
            for the given codes.
    """
    assert response.status_code == status_code
    response_header_keys = {
        'Connection',
        'Content-Length',
        'Date',
        'Server',
    }

    if cache_control is not None:
        response_header_keys.add('Cache-Control')
        assert response.headers['Cache-Control'] == cache_control

    if content_type is not None:
        response_header_keys.add('Content-Type')
        assert response.headers['Content-Type'] == content_type

    if www_authenticate is not None:
        response_header_keys.add('WWW-Authenticate')
        assert response.headers['WWW-Authenticate'] == www_authenticate

    assert response.headers.keys() == response_header_keys
    assert response.headers['Connection'] == 'keep-alive'
    assert response.headers['Content-Length'] == str(len(response.text))
    assert_valid_date_header(response=response)
    assert response.headers['Server'] == 'nginx'
