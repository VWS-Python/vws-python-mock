"""Assertions shared by Model Target Web API tests."""

import json
from http import HTTPStatus

import requests
from beartype import beartype
from vws.response import Response

from tests.mock_vws.utils.assertions import assert_model_target_status


@beartype
def assert_oauth2_error(
    *,
    response: requests.Response,
    status_code: HTTPStatus,
    body: dict[str, str],
) -> None:
    """Assert an OAuth2 error response."""
    assert_model_target_status(
        response=response,
        status_codes=status_code,
    )
    assert response.json() == body


@beartype
def assert_model_target_error(
    *,
    response: Response,
    status_code: HTTPStatus,
    code: str,
    message: str,
    target: str,
) -> None:
    """Assert a Model Target Web API error response with the legacy
    shape.
    """
    assert_model_target_status(
        response=response,
        status_codes=status_code,
    )
    assert json.loads(s=response.text) == {
        "error": {
            "code": code,
            "message": message,
            "target": target,
        },
    }
