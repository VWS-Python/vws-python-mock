"""Shared helpers for requests tests."""

import textwrap
from http import HTTPStatus
from typing import TypedDict

import requests
from beartype import beartype
from pydantic import TypeAdapter
from vws.response import Response

from tests.mock_vws.fixtures.model_target_prepared_requests import (
    MODEL_TARGET_DATASET_UUID,
)
from tests.mock_vws.model_target_web_api.responses import (
    Error,
    response_targeted_error,
)
from tests.mock_vws.utils.assertions import (
    assert_model_target_status,
    assert_valid_date_header,
)


class _ErrorResponse(TypedDict):
    """A Model Target API error response."""

    error: Error


@beartype
def response_error(*, response: requests.Response | Response) -> Error:
    """Validate and return a Model Target API error response."""
    body = TypeAdapter(type=_ErrorResponse).validate_json(response.text)
    return body["error"]


@beartype
def assert_load_balancer_bad_request(*, response: Response) -> None:
    """Assert the ``BAD_REQUEST`` response from the load balancer.

    The load balancer in front of Vuforia rejects some requests before
    they reach an API, with an HTML error page rather than a Model Target
    Web API error body.
    """
    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.BAD_REQUEST,
    )
    assert_valid_date_header(response=response)
    expected_response_text = textwrap.dedent(
        text="""\
        <html>\r
        <head><title>400 Bad Request</title></head>\r
        <body>\r
        <center><h1>400 Bad Request</h1></center>\r
        </body>\r
        </html>\r
        """,
    )
    assert response.text == expected_response_text
    assert response.headers == {
        "Content-Length": str(object=len(response.text)),
        "Content-Type": "text/html",
        "Connection": "close",
        "Server": "awselb/2.0",
        "Date": response.headers["Date"],
    }


@beartype
def assert_unknown_dataset(*, response: Response) -> None:
    """Assert a NOT_FOUND error for the unknown dataset UUID which the
    prepared requests use.

    The body-less Model Target endpoints ignore any request body, so a
    request with a valid bearer token and an unexpected or malformed body
    reaches the dataset lookup.
    """
    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.NOT_FOUND,
    )
    error = response_targeted_error(response=response)
    assert error["code"] == "NOT_FOUND"
    assert error["message"] == (
        "Could not find a model-view database with uuid "
        f"{MODEL_TARGET_DATASET_UUID}"
    )
    # The user-id portion is per-account in real Vuforia, so check only
    # the stable prefix.
    assert error["target"].startswith("userId:")
