"""Tests for the order of query results."""

import io
import json
import uuid

import pytest
from vws import VWS

from mock_vws.database import CloudDatabase
from tests.mock_vws.query.helpers import (
    query,
)
from tests.mock_vws.utils.assertions import (
    assert_query_success,
)
from tests.mock_vws.utils.backend_capabilities import BackendCapabilities


def test_order_is_upload_date_then_target_id(
    *,
    backend_capabilities: BackendCapabilities,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
    vuforia_database: CloudDatabase,
    base_vwq_url: str,
) -> None:
    """Matches with the same score are ordered by upload date.

    Every target here has the same image, so the mock's image matcher
    gives them all the same score and the tie-break decides the order.
    The real Query API scores matches with Vuforia's own proprietary
    matcher, so we do not verify this against the real Vuforia Web
    Services.
    """
    if not backend_capabilities.deterministic_query_order:
        pytest.skip(
            reason="This backend does not guarantee query upload-date order.",
        )

    target_ids = [
        vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        for _ in range(3)
    ]

    for target_id in target_ids:
        vws_client.wait_for_target_processed(target_id=target_id)

    image_content = high_quality_image.getvalue()
    body = {
        "image": ("image.jpeg", image_content, "image/jpeg"),
        "max_num_results": (None, 3, "text/plain"),
    }

    response = query(
        vuforia_database=vuforia_database, body=body, base_vwq_url=base_vwq_url
    )

    assert_query_success(response=response)
    response_json = json.loads(s=response.text)
    result_target_ids = [
        result["target_id"] for result in response_json["results"]
    ]
    assert result_target_ids == target_ids


def test_max_num_results_keeps_the_first_results(
    *,
    backend_capabilities: BackendCapabilities,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
    vuforia_database: CloudDatabase,
    base_vwq_url: str,
) -> None:
    """``max_num_results`` truncates a deterministically ordered
    list.

    Which matches survive the truncation therefore does not vary
    between runs.
    """
    if not backend_capabilities.deterministic_query_order:
        pytest.skip(
            reason="This backend does not guarantee query upload-date order.",
        )

    target_ids = [
        vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        for _ in range(3)
    ]

    for target_id in target_ids:
        vws_client.wait_for_target_processed(target_id=target_id)

    image_content = high_quality_image.getvalue()
    body = {
        "image": ("image.jpeg", image_content, "image/jpeg"),
        "max_num_results": (None, 1, "text/plain"),
    }

    response = query(
        vuforia_database=vuforia_database, body=body, base_vwq_url=base_vwq_url
    )

    assert_query_success(response=response)
    response_json = json.loads(s=response.text)
    (result,) = response_json["results"]
    assert result["target_id"] == target_ids[0]
