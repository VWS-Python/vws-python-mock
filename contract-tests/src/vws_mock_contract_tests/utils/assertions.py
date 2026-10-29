"""Assertion helpers."""

import datetime as dt
import email.utils
import json
from collections.abc import Set as AbstractSet
from http import HTTPStatus
from string import hexdigits
from zoneinfo import ZoneInfo

import requests
from beartype import beartype
from vws.response import Response

from vws_mock_contract_tests.utils.model_target_response_policy import (
    handle_unexpected_model_target_response,
)


@beartype
def assert_vws_failure(
    *,
    response: Response,
    status_code: int,
    result_code: str,
) -> None:
    """Assert that a VWS failure response is as expected.

    Args:
        response: The response returned by a request to VWS.
        status_code: The expected status code of the response.
        result_code: The expected result code of the response.

    Raises:
        AssertionError: The response is not in the expected VWS error format
            for the given codes.
    """
    assert json.loads(s=response.text).keys() == {
        "transaction_id",
        "result_code",
    }
    assert_vws_response(
        response=response,
        status_code=status_code,
        result_code=result_code,
    )


@beartype
def assert_valid_date_header(
    *,
    response: Response,
) -> None:
    """Assert that a response includes a `Date` header which is within two
    minutes of "now".

    Args:
        response: The response returned by a request to a Vuforia service.

    Raises:
        AssertionError: The response does not include a `Date` header which is
            within one minute of "now".
    """
    date_response = response.headers["Date"]
    date_from_response = email.utils.parsedate(data=date_response)
    assert date_from_response is not None
    year, month, day, hour, minute, second, _, _, _ = date_from_response
    gmt = ZoneInfo(key="GMT")
    datetime_from_response = dt.datetime(
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        second=second,
        tzinfo=gmt,
    )
    current_date = dt.datetime.now(tz=gmt)
    time_difference = abs(current_date - datetime_from_response)
    assert time_difference < dt.timedelta(minutes=2)


@beartype
def assert_valid_transaction_id(
    *,
    response: Response,
) -> None:
    """Assert that a response includes a valid transaction ID.

    Args:
        response: The response returned by a request to a Vuforia service.

    Raises:
        AssertionError: The response does not include a valid transaction ID.
    """
    response_json = json.loads(s=response.text)
    assert isinstance(response_json, dict)
    assert isinstance(response_json["transaction_id"], str)
    transaction_id: str = response_json["transaction_id"]
    expected_transaction_id_length = 32
    assert len(transaction_id) == expected_transaction_id_length
    assert all(char in hexdigits for char in transaction_id)


@beartype
def assert_json_separators(*, response: Response) -> None:
    """Assert that a JSON response is formatted correctly.

    Args:
        response: The response returned by a request to a Vuforia service.

    Raises:
        AssertionError: The response JSON is not formatted correctly.
    """
    assert response.text == json.dumps(
        obj=json.loads(s=response.text),
        separators=(",", ":"),
    )


@beartype
def assert_vws_response(
    *,
    response: Response,
    status_code: int,
    result_code: str,
) -> None:
    """Assert that a VWS response is as expected, at least in part.

    https://developer.vuforia.com/library/web-api/cloud-targets-web-services-api#result-codes
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
    response_json = json.loads(s=response.text)
    assert isinstance(response_json, dict)
    assert isinstance(response_json["result_code"], str)
    response_result_code: str = response_json["result_code"]
    assert response_result_code == result_code
    response_header_keys = {
        "connection",
        "content-length",
        "content-type",
        "date",
        "server",
        "strict-transport-security",
        "x-aws-region",
        "x-content-type-options",
        "x-envoy-upstream-service-time",
    }
    assert {str.lower(key) for key in response.headers} == response_header_keys
    assert response.headers["Content-Length"] == str(object=len(response.text))
    assert response.headers["Content-Type"] == "application/json"
    assert response.headers["server"] == "envoy"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "-" in response.headers["x-aws-region"]
    assert response.headers["strict-transport-security"] == "max-age=31536000"
    assert int(response.headers["x-envoy-upstream-service-time"]) > 1
    assert response.headers["Connection"] == "keep-alive"
    assert_json_separators(response=response)
    assert_valid_transaction_id(response=response)
    assert_valid_date_header(response=response)


@beartype
def assert_model_target_status(
    *,
    response: Response | requests.Response,
    status_codes: HTTPStatus | AbstractSet[HTTPStatus],
) -> None:
    """Assert the status code of a Model Target Web API response.

    An unexpected status reports the URL and body. A backend may supply
    a response handler for restrictions of the service it runs against.

    Args:
        response: The response returned by a request to the Model Target Web
            API.
        status_codes: The expected status code, or the status codes any of
            which is expected.

    Raises:
        AssertionError: The response does not have one of the expected status
            codes and the backend handler has not handled the rejection.
    """
    expected = (
        frozenset({status_codes})
        if isinstance(status_codes, HTTPStatus)
        else frozenset(status_codes)
    )
    if response.status_code in expected:
        return

    handle_unexpected_model_target_response(response=response)
    expected_description = " or ".join(
        sorted(f"{item} {item.name}" for item in expected)
    )
    message = (
        f"Expected {expected_description} from {response.url}, "
        f"got {response.status_code}.\n\nResponse body:\n{response.text}"
    )
    raise AssertionError(message)
