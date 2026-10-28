"""Shared helpers for update target tests."""

import json
from collections.abc import Mapping
from http import HTTPMethod
from typing import Final

from vws import VWS
from vws.response import Response

MAX_METADATA_BYTES: Final[int] = 1024 * 1024 - 1


def update_target(
    *,
    vws_client: VWS,
    data: Mapping[str, object],
    target_id: str,
    content_type: str,
) -> Response:
    """Make a request to the endpoint to update a target.

    Args:
        vws_client: The client to use to connect to Vuforia.
        data: The data to send, in JSON format, to the endpoint.
        target_id: The ID of the target to update.
        content_type: The `Content-Type` header to use.

    Returns:
        The response returned by the API.
    """
    content = json.dumps(obj=data).encode(encoding="utf-8")
    return vws_client.make_request(
        method=HTTPMethod.PUT,
        data=content,
        request_path=f"/targets/{target_id}",
        expected_result_code="Success",
        content_type=content_type,
    )
