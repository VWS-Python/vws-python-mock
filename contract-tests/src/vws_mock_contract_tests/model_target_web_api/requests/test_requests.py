"""Additional requests tests."""

import dataclasses
from http import HTTPStatus

import pytest

from vws_mock_contract_tests.fixtures.credentials import ModelTargetCredentials
from vws_mock_contract_tests.fixtures.model_target_prepared_requests import (
    get_access_token,
)
from vws_mock_contract_tests.model_target_web_api.requests.helpers import (
    assert_unknown_dataset,
    response_error,
)
from vws_mock_contract_tests.model_target_web_api.responses import (
    response_validation_error,
)
from vws_mock_contract_tests.utils import ModelTargetEndpoint
from vws_mock_contract_tests.utils.assertions import (
    assert_model_target_status,
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
    model_target_credentials: ModelTargetCredentials,
    base_vws_url: str,
    model_target_endpoint: ModelTargetEndpoint,
    content_type: str | None,
) -> None:
    """Requests without a JSON content type are rejected with 415 by
    endpoints which read a body, and are unaffected elsewhere.
    """
    access_token = get_access_token(
        base_vws_url=base_vws_url,
        credentials=model_target_credentials,
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
        assert_unknown_dataset(response=response)
        return

    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
    )
    error = response_error(response=response)
    assert error["code"] == "ERROR"
    assert error["message"] == ("Expecting text/json or application/json body")
    assert "target" not in error


def test_invalid_json(
    *,
    model_target_credentials: ModelTargetCredentials,
    base_vws_url: str,
    model_target_endpoint: ModelTargetEndpoint,
) -> None:
    """Malformed JSON bodies are rejected with 400 by endpoints which
    read a body, and are ignored elsewhere.
    """
    access_token = get_access_token(
        base_vws_url=base_vws_url,
        credentials=model_target_credentials,
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
        assert_unknown_dataset(response=response)
        return

    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.BAD_REQUEST,
    )
    error = response_error(response=response)
    assert error["code"] == "ERROR"
    assert error["message"].startswith("Invalid Json")
    assert "target" not in error


def test_body_not_utf_8(
    *,
    model_target_credentials: ModelTargetCredentials,
    base_vws_url: str,
    model_target_endpoint: ModelTargetEndpoint,
) -> None:
    """Bodies which are not valid UTF-8 are rejected with 400 by
    endpoints which read a body, and are ignored elsewhere.
    """
    access_token = get_access_token(
        base_vws_url=base_vws_url,
        credentials=model_target_credentials,
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
        assert_unknown_dataset(response=response)
        return

    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.BAD_REQUEST,
    )
    error = response_error(response=response)
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
    model_target_credentials: ModelTargetCredentials,
    base_vws_url: str,
    model_target_endpoint: ModelTargetEndpoint,
    body: str,
) -> None:
    """JSON bodies which are not objects are missing every field on
    endpoints which read a body, and are ignored elsewhere.
    """
    access_token = get_access_token(
        base_vws_url=base_vws_url,
        credentials=model_target_credentials,
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
        assert_unknown_dataset(response=response)
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
