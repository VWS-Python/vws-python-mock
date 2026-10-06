"""Tests for requests through the Model Target Web API."""

import dataclasses
import textwrap
from http import HTTPMethod, HTTPStatus
from typing import TypedDict

import pytest
import requests
from beartype import beartype
from pydantic import TypeAdapter
from vws.response import Response

from tests.mock_vws.fixtures.model_target_prepared_requests import (
    MODEL_TARGET_DATASET_UUID,
)
from tests.mock_vws.fixtures.vuforia_backends import (
    VuforiaBackend,
)
from tests.mock_vws.model_target_web_api.helpers import (
    VWS_HOST,
    Error,
    access_token_for_backend,
    assert_model_target_error,
    response_targeted_error,
    response_validation_error,
)
from tests.mock_vws.utils import ModelTargetEndpoint
from tests.mock_vws.utils.assertions import (
    assert_model_target_status,
    assert_valid_date_header,
)


class _ErrorResponse(TypedDict):
    """A Model Target API error response."""

    error: Error


@beartype
def _response_error(*, response: requests.Response | Response) -> Error:
    """Validate and return a Model Target API error response."""
    body = TypeAdapter(type=_ErrorResponse).validate_json(response.text)
    return body["error"]


@beartype
def _assert_load_balancer_bad_request(*, response: Response) -> None:
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
def _assert_unknown_dataset(*, response: Response) -> None:
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


@pytest.mark.usefixtures("verify_model_target_mock_vuforia")
class TestContentLength:
    """Tests for the ``Content-Length`` header on every Model Target
    endpoint.

    These mirror the cross-cutting tests which the ``endpoint`` fixture
    supports for the VWS and Query APIs.

    A ``Content-Length`` header which is too large is not covered, for the
    same reason as it is not covered for the VWS API: real Vuforia waits
    for the body it was promised before timing out, which takes too long
    to run in a test.
    """

    @staticmethod
    def test_not_integer(
        *,
        model_target_endpoint: ModelTargetEndpoint,
    ) -> None:
        """A ``Content-Length`` header which is not an integer is rejected
        by the load balancer in front of Vuforia, before any bearer token
        is looked at.
        """
        new_endpoint = dataclasses.replace(
            model_target_endpoint,
            headers={
                **model_target_endpoint.headers,
                "Content-Length": "0.4",
            },
        )

        response = new_endpoint.send()

        _assert_load_balancer_bad_request(response=response)

    @staticmethod
    def test_not_integer_oauth2_token() -> None:
        """The OAuth2 token endpoint is behind the same load balancer.

        It is not in the ``model_target_endpoint`` fixture because it takes
        HTTP Basic credentials rather than a bearer token.
        """
        endpoint = ModelTargetEndpoint(
            base_url=VWS_HOST,
            path_url="/oauth2/token",
            method=HTTPMethod.POST,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Content-Length": "0.4",
            },
            data=b"grant_type=client_credentials",
            takes_json_body=False,
        )

        response = endpoint.send()

        _assert_load_balancer_bad_request(response=response)

    @staticmethod
    def test_too_small(
        *,
        model_target_endpoint: ModelTargetEndpoint,
    ) -> None:
        """A ``Content-Length`` header which is too small truncates the
        body, and the request is still rejected for having no bearer
        token.

        The Model Target Web API does not sign the request body, so unlike
        the VWS API it has no reason to notice the truncation before it
        looks at the ``Authorization`` header.
        """
        if not model_target_endpoint.takes_json_body:
            return

        content_length = len(model_target_endpoint.data) - 1
        new_endpoint = dataclasses.replace(
            model_target_endpoint,
            headers={
                **model_target_endpoint.headers,
                "Content-Length": str(object=content_length),
            },
        )

        response = new_endpoint.send()

        assert_model_target_error(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message="no Bearer token",
            target="jwt",
        )


@pytest.mark.parametrize(
    argnames="content_type",
    argvalues=[
        pytest.param(None, id="missing"),
        pytest.param("", id="empty"),
    ],
)
def test_wrong_content_type(
    *,
    verify_model_target_mock_vuforia: VuforiaBackend,
    model_target_endpoint: ModelTargetEndpoint,
    content_type: str | None,
) -> None:
    """Requests without a JSON content type are rejected with 415 by
    endpoints which read a body, and are unaffected elsewhere.
    """
    access_token = access_token_for_backend(
        backend=verify_model_target_mock_vuforia,
    )
    new_headers = {
        **model_target_endpoint.headers,
        "Authorization": f"Bearer {access_token}",
    }
    if content_type is None:
        _ = new_headers.pop("Content-Type", None)
    else:
        new_headers["Content-Type"] = content_type
    new_endpoint = dataclasses.replace(
        model_target_endpoint,
        headers=new_headers,
    )

    response = new_endpoint.send()

    if not model_target_endpoint.takes_json_body:
        _assert_unknown_dataset(response=response)
        return

    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
    )
    error = _response_error(response=response)
    assert error["code"] == "ERROR"
    assert error["message"] == ("Expecting text/json or application/json body")
    assert "target" not in error


def test_invalid_json(
    *,
    verify_model_target_mock_vuforia: VuforiaBackend,
    model_target_endpoint: ModelTargetEndpoint,
) -> None:
    """Malformed JSON bodies are rejected with 400 by endpoints which
    read a body, and are ignored elsewhere.
    """
    access_token = access_token_for_backend(
        backend=verify_model_target_mock_vuforia,
    )
    content = b"{"
    new_endpoint = dataclasses.replace(
        model_target_endpoint,
        headers={
            **model_target_endpoint.headers,
            "Authorization": f"Bearer {access_token}",
            "Content-Length": str(object=len(content)),
        },
        data=content,
    )

    response = new_endpoint.send()

    if not model_target_endpoint.takes_json_body:
        _assert_unknown_dataset(response=response)
        return

    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.BAD_REQUEST,
    )
    error = _response_error(response=response)
    assert error["code"] == "ERROR"
    assert error["message"].startswith("Invalid Json")
    assert "target" not in error


def test_body_not_utf_8(
    *,
    verify_model_target_mock_vuforia: VuforiaBackend,
    model_target_endpoint: ModelTargetEndpoint,
) -> None:
    """Bodies which are not valid UTF-8 are rejected with 400 by
    endpoints which read a body, and are ignored elsewhere.
    """
    access_token = access_token_for_backend(
        backend=verify_model_target_mock_vuforia,
    )
    content = b"\xff{}"
    new_endpoint = dataclasses.replace(
        model_target_endpoint,
        headers={
            **model_target_endpoint.headers,
            "Authorization": f"Bearer {access_token}",
            "Content-Length": str(object=len(content)),
        },
        data=content,
    )

    response = new_endpoint.send()

    if not model_target_endpoint.takes_json_body:
        _assert_unknown_dataset(response=response)
        return

    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.BAD_REQUEST,
    )
    error = _response_error(response=response)
    assert error["code"] == "ERROR"
    assert error["message"].startswith("Invalid Json")
    assert "target" not in error


@pytest.mark.parametrize(
    argnames="body",
    argvalues=[
        pytest.param("[]", id="array"),
        pytest.param('"dataset"', id="string"),
        pytest.param("1", id="number"),
        pytest.param("true", id="boolean"),
        pytest.param("null", id="null"),
    ],
)
def test_body_not_json_object(
    *,
    verify_model_target_mock_vuforia: VuforiaBackend,
    model_target_endpoint: ModelTargetEndpoint,
    body: str,
) -> None:
    """JSON bodies which are not objects are missing every field on
    endpoints which read a body, and are ignored elsewhere.
    """
    access_token = access_token_for_backend(
        backend=verify_model_target_mock_vuforia,
    )
    content = body.encode(encoding="utf-8")
    new_endpoint = dataclasses.replace(
        model_target_endpoint,
        headers={
            **model_target_endpoint.headers,
            "Authorization": f"Bearer {access_token}",
            "Content-Length": str(object=len(content)),
        },
        data=content,
    )

    response = new_endpoint.send()

    if not model_target_endpoint.takes_json_body:
        _assert_unknown_dataset(response=response)
        return

    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.BAD_REQUEST,
    )
    error = response_validation_error(response=response)
    assert error["code"] == "BAD_REQUEST"
    assert error["message"] == (
        f"Validation error for request {error['target']}"
    )
    actual_messages = {detail["message"] for detail in error["details"]}
    assert actual_messages == {
        "/models: element is required",
        "/name: element is required",
        "/targetSdk: element is required",
    }
    for detail in error["details"]:
        assert detail["code"] == "VALIDATION_ERROR"
