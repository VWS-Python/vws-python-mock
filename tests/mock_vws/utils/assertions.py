"""Assertion helpers."""

import copy
import datetime
import email.utils
import json
import textwrap
from collections.abc import Set as AbstractSet
from http import HTTPStatus
from string import hexdigits
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pytest
import requests
from beartype import beartype
from vws.response import Response

from mock_vws._constants import ResultCodes


@beartype
def assert_vws_failure(
    *,
    response: Response,
    status_code: int,
    result_code: ResultCodes,
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
def assert_vws_too_many_requests(*, response: Response) -> None:
    """Assert that a response is the rate-limited response which real
    Vuforia's Envoy layer gives.

    The response has no body and no ``Content-Type`` header. Real Vuforia
    has an Envoy layer at its edge and another in front of the application,
    and either may reject the request. Only a rejection by the inner layer
    carries an ``x-envoy-upstream-service-time`` header. This was observed
    against real Vuforia on 2026-09-08.

    Args:
        response: The response returned by a request to VWS.

    Raises:
        AssertionError: The response is not the rate-limited response.
    """
    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert response.text == ""
    required_header_keys = {
        "connection",
        "content-length",
        "date",
        "server",
        "strict-transport-security",
        "x-aws-region",
        "x-content-type-options",
        "x-envoy-ratelimited",
    }
    optional_header_keys = {"x-envoy-upstream-service-time"}
    response_header_keys = {str.lower(key) for key in response.headers}
    assert required_header_keys <= response_header_keys
    assert response_header_keys <= required_header_keys | optional_header_keys
    assert response.headers["Content-Length"] == "0"
    assert response.headers["server"] == "envoy"
    assert response.headers["x-envoy-ratelimited"] == "true"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "-" in response.headers["x-aws-region"]
    assert response.headers["strict-transport-security"] == "max-age=31536000"
    assert_valid_date_header(response=response)


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
    result_code: ResultCodes,
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
    assert response_result_code == result_code.value
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


_TRAINING_ALLOWANCE_EXCEEDED = "TRAINING_ALLOWANCE_EXCEEDED"

# The first line of the failure message, because a truncated failure summary
# in a CI log has to be enough to tell this apart from a real regression.
_TRAINING_ALLOWANCE_EXCEEDED_HEADLINE = (
    "The Vuforia account is out of Model Target training allowance - "
    "this is not a failure of the code under test."
)

_TRAINING_ALLOWANCE_EXCEEDED_EXPLANATION = textwrap.dedent(
    text="""\
    ``TRAINING_ALLOWANCE_EXCEEDED`` is a quota on the Vuforia account behind
    ``MODEL_TARGET_VUFORIA_CLIENT_ID``, not a fault in the code under test or
    in this request. Every CI job shares one set of Model Target credentials,
    so the allowance is consumed across all jobs and all concurrent runs.

    The allowance has to be raised, or reset, on the Vuforia account for this
    request to succeed against the real backend again. Signed dataset types,
    such as an advanced dataset with a state-based configuration, exhaust it
    first, but with enough traffic unsigned dataset creation is rejected too.

    An unexpected allowance rejection is reported as an expected failure
    (xfail) rather than a test failure, so that the shared account running
    dry does not turn CI red: the test passes again automatically once the
    allowance recovers.""",
)


@beartype
def assert_model_target_status(
    *,
    response: Response | requests.Response,
    status_codes: HTTPStatus | AbstractSet[HTTPStatus],
) -> None:
    """Assert the status code of a Model Target Web API response.

    A bare ``assert response.status_code == ...`` hides the response body,
    which is where the real Model Target Web API says *why* it rejected a
    request. That matters most when the reason has nothing to do with the
    request, such as an exhausted account allowance, so this helper always
    reports the body and calls out that case by name.

    Args:
        response: The response returned by a request to the Model Target Web
            API.
        status_codes: The expected status code, or the status codes any of
            which is expected.

    Raises:
        AssertionError: The response does not have one of the expected status
            codes.
        Exception: The response unexpectedly reports a
            ``TRAINING_ALLOWANCE_EXCEEDED`` rejection. That is the shared
            Vuforia account running out of Model Target training allowance,
            not a fault in the code under test, so it is an expected failure
            rather than a test failure.
    """
    expected = (
        frozenset({status_codes})
        if isinstance(status_codes, HTTPStatus)
        else frozenset(status_codes)
    )
    if response.status_code in expected:
        return

    expected_description = " or ".join(
        sorted(f"{item} {item.name}" for item in expected)
    )
    allowance_exceeded = _TRAINING_ALLOWANCE_EXCEEDED in response.text
    if (
        allowance_exceeded
        and urlparse(url=response.url).hostname == "vws.vuforia.com"
    ):
        pytest.skip(reason=_TRAINING_ALLOWANCE_EXCEEDED_HEADLINE)
    headline = (
        [_TRAINING_ALLOWANCE_EXCEEDED_HEADLINE] if allowance_exceeded else []
    )
    explanation = (
        [_TRAINING_ALLOWANCE_EXCEEDED_EXPLANATION]
        if allowance_exceeded
        else []
    )
    message = "\n\n".join(
        [
            *headline,
            (
                f"Expected {expected_description} from {response.url}, "
                f"got {response.status_code}."
            ),
            f"Response body:\n{response.text}",
            *explanation,
        ],
    )
    if allowance_exceeded:
        pytest.xfail(reason=message)
    raise AssertionError(message)


@beartype
def assert_query_success(*, response: Response) -> None:
    """Assert that the given response is a success response for performing
    an
    image recognition query.

    Raises:
        AssertionError: The given response is not a valid success response
            for performing an image recognition query.
    """
    assert response.status_code == HTTPStatus.OK
    assert json.loads(s=response.text).keys() == {
        "result_code",
        "results",
        "query_id",
    }

    response_json = json.loads(s=response.text)
    assert isinstance(response_json, dict)
    assert isinstance(response_json["query_id"], str)
    query_id: str = response_json["query_id"]
    expected_query_id_length = 32
    assert len(query_id) == expected_query_id_length
    assert all(char in hexdigits for char in query_id)

    assert json.loads(s=response.text)["result_code"] == "Success"
    assert_valid_date_header(response=response)
    copied_response_headers = response.headers.copy()
    _ = copied_response_headers.pop("Date")

    # In the mock, all responses have the ``Content-Encoding`` ``gzip``.
    # In the real Vuforia, some do and some do not.
    # We are not sure why.
    content_encoding = copied_response_headers.pop("Content-Encoding", None)
    assert content_encoding in {None, "gzip"}

    expected_response_header_not_chunked = {
        "Connection": "keep-alive",
        "Content-Length": str(object=response.tell_position),
        "Content-Type": "application/json",
        "Server": "nginx",
    }

    # The mock does not send chunked responses.
    expected_response_header_chunked = {
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Server": "nginx",
        "transfer-encoding": "chunked",
    }

    assert copied_response_headers in (
        expected_response_header_chunked,
        expected_response_header_not_chunked,
    )


@beartype
def assert_vwq_failure(
    *,
    response: Response,
    status_code: int,
    content_type: str | None,
    cache_control: str | None,
    www_authenticate: str | None,
    connection: str,
) -> None:
    """Assert that a VWQ failure response is as expected.

    Args:
        response: The response returned by a request to VWQ.
        content_type: The expected Content-Type header.
        status_code: The expected status code.
        cache_control: The expected Cache-Control header.
        www_authenticate: The expected WWW-Authenticate header.
        connection: The expected Connection header.

    Raises:
        AssertionError: The response is not in the expected VWQ error format
            for the given codes.
    """
    assert response.status_code == status_code
    response_header_keys = {
        "Connection",
        "Content-Length",
        "Date",
        "Server",
    }

    if cache_control is not None:
        response_header_keys.add("Cache-Control")
        assert response.headers["Cache-Control"] == cache_control

    if content_type is not None:
        response_header_keys.add("Content-Type")
        assert response.headers["Content-Type"] == content_type

    if www_authenticate is not None:
        response_header_keys.add("WWW-Authenticate")
        assert response.headers["WWW-Authenticate"] == www_authenticate

    # Sometimes the "transfer-encoding" is given.
    # It is not given by the mock.
    response_header_keys_chunked = copy.copy(x=response_header_keys)
    response_header_keys_chunked.remove("Content-Length")
    response_header_keys_chunked.add("transfer-encoding")

    assert response.headers.keys() in (
        response_header_keys,
        response_header_keys_chunked,
    )
    assert response.headers.get("transfer-encoding", "chunked") == "chunked"
    assert response.headers["Connection"] == connection
    content_length = response.headers.get("Content-Length")
    assert content_length is None or content_length == str(
        object=len(response.text)
    )
    assert_valid_date_header(response=response)
    assert response.headers["Server"] == "nginx"
