"""Tests for the mock of the target list endpoint at `/targets`."""

import io
import uuid

import pytest
from vws import VWS

from tests.mock_vws.utils.backend_capabilities import BackendCapabilities


def test_includes_targets(
    *,
    vws_client: VWS,
    unprocessed_target_id: str,
) -> None:
    """Targets in the database are returned in the list."""
    assert vws_client.list_targets() == [unprocessed_target_id]


def test_deleted(
    *,
    vws_client: VWS,
    target_id: str,
) -> None:
    """Deleted targets are not returned in the list."""
    vws_client.delete_target(target_id=target_id)
    assert not bool(vws_client.list_targets())


def test_order_is_upload_date_then_target_id(
    *,
    backend_capabilities: BackendCapabilities,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
) -> None:
    """The mock returns targets ordered by upload date.

    The real Vuforia Web Services do not document an order, so we do
    not verify this against them.
    """
    if not backend_capabilities.deterministic_target_order:
        pytest.skip(
            reason="This backend does not guarantee target upload-date order."
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

    assert vws_client.list_targets() == target_ids
