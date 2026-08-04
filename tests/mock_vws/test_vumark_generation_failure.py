"""Tests for configurable VuMark generation failures."""

from collections.abc import Callable
from http import HTTPStatus

import httpx
import pytest
import requests

from mock_vws import MockVWS, VuMarkGenerationFailure

_VUMARK_URL = "https://vws.vuforia.com/targets/example/instances"
_REQUEST_BODY = b'{"instance_id":"example"}'
type _HTTPResponse = requests.Response | httpx.Response
type _RequestSender = Callable[[], _HTTPResponse]


def _requests_request() -> _HTTPResponse:
    """Send a VuMark generation request with ``requests``."""
    return requests.post(
        url=_VUMARK_URL,
        headers={
            "Accept": "image/png",
            "Content-Type": "application/json",
        },
        data=_REQUEST_BODY,
        timeout=30,
    )


def _httpx_request() -> _HTTPResponse:
    """Send a VuMark generation request with ``httpx``."""
    return httpx.post(
        url=_VUMARK_URL,
        headers={
            "Accept": "image/png",
            "Content-Type": "application/json",
        },
        content=_REQUEST_BODY,
        timeout=30,
    )


@pytest.mark.parametrize(
    argnames="send_request",
    argvalues=[_requests_request, _httpx_request],
    ids=["requests", "httpx"],
)
@pytest.mark.parametrize(
    argnames=("failure", "expected_status_code"),
    argvalues=[
        (
            VuMarkGenerationFailure.QUOTA_EXCEEDED,
            HTTPStatus.FORBIDDEN,
        ),
        (
            VuMarkGenerationFailure.LICENSE_CHECK_FAILED,
            HTTPStatus.FORBIDDEN,
        ),
        (
            VuMarkGenerationFailure.AUTHORIZATION_FAILED,
            HTTPStatus.UNAUTHORIZED,
        ),
    ],
)
def test_configured_failure_response(
    *,
    send_request: _RequestSender,
    failure: VuMarkGenerationFailure,
    expected_status_code: HTTPStatus,
) -> None:
    """Both in-process backends return the configured failure."""
    with MockVWS(vumark_generation_failure=failure):
        response = send_request()

    assert response.status_code == expected_status_code
    assert response.headers["Content-Type"] == "application/json"
    assert response.json()["result_code"] == failure.value
    assert response.json()["transaction_id"]
