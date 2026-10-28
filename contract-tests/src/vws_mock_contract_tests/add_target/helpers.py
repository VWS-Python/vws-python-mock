"""Shared helpers for add target tests."""

import json
from collections.abc import Mapping
from http import HTTPMethod, HTTPStatus
from string import hexdigits
from typing import Final

from beartype import beartype
from vws import VWS
from vws.response import Response

from vws_mock_contract_tests.utils.assertions import (
    assert_vws_response,
)

MAX_METADATA_BYTES: Final[int] = 1024 * 1024 - 1


@beartype
def add_target_to_vws(
    *,
    vws_client: VWS,
    data: Mapping[str, object],
    content_type: str,
) -> Response:
    """Return a response from a request to the endpoint to add a target.

    Args:
        vws_client: The client to use to connect to Vuforia.
        data: The data to send, in JSON format, to the endpoint.
        content_type: The `Content-Type` header to use.

    Returns:
        The response returned by the API.
    """
    content = json.dumps(obj=data).encode(encoding="utf-8")
    return vws_client.make_request(
        method=HTTPMethod.POST,
        data=content,
        request_path="/targets",
        expected_result_code="TargetCreated",
        content_type=content_type,
    )


def assert_success(response: Response) -> None:
    """Assert that the given response is a success response for adding a
    target.

    Raises:
        AssertionError: The given response is not a valid success response
            for adding a target.
    """
    assert_vws_response(
        response=response,
        status_code=HTTPStatus.CREATED,
        result_code="TargetCreated",
    )
    expected_keys = {"result_code", "transaction_id", "target_id"}
    response_json = json.loads(s=response.text)
    assert isinstance(response_json, dict)
    assert isinstance(response_json["target_id"], str)
    target_id: str = response_json["target_id"]
    expected_target_id_length = 32
    assert len(target_id) == expected_target_id_length
    assert all(char in hexdigits for char in target_id)
    assert response_json.keys() == expected_keys
