"""Tests for the mock of the target duplicates endpoint."""

import copy
import io
import uuid

import pytest
from PIL import Image
from vws import VWS
from vws.reports import TargetStatuses

from vws_mock_contract_tests.utils.backend_capabilities import (
    BackendCapabilities,
)


def test_duplicates(
    *,
    high_quality_image: io.BytesIO,
    image_file_success_state_low_rating: io.BytesIO,
    vws_client: VWS,
) -> None:
    """Target IDs of the exact same targets are returned."""
    image_data = high_quality_image
    different_image_data = image_file_success_state_low_rating

    original_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_data,
        active_flag=True,
        application_metadata=None,
    )

    similar_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_data,
        active_flag=True,
        application_metadata=None,
    )

    different_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=different_image_data,
        active_flag=True,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=original_target_id)
    vws_client.wait_for_target_processed(target_id=similar_target_id)
    vws_client.wait_for_target_processed(target_id=different_target_id)

    duplicates = vws_client.get_duplicate_targets(
        target_id=original_target_id,
    )

    assert duplicates == [similar_target_id]


def test_duplicates_not_same(
    *,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
) -> None:
    """Target IDs of similar targets are returned."""
    image_data = high_quality_image
    similar_image_data = copy.copy(x=image_data)
    similar_image_buffer = io.BytesIO()
    pil_similar_image = Image.open(fp=similar_image_data)
    # Re-save means similar but not identical.
    pil_similar_image.save(fp=similar_image_buffer, format="JPEG")
    assert similar_image_buffer.getvalue() != image_data.getvalue()

    original_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_data,
        active_flag=True,
        application_metadata=None,
    )

    similar_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=similar_image_buffer,
        active_flag=True,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=original_target_id)
    vws_client.wait_for_target_processed(target_id=similar_target_id)

    duplicates = vws_client.get_duplicate_targets(
        target_id=original_target_id,
    )

    assert duplicates == [similar_target_id]


def test_status(
    *,
    image_file_failed_state: io.BytesIO,
    vws_client: VWS,
) -> None:
    """Targets are not duplicates if the status is not 'success'."""
    original_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_file_failed_state,
        active_flag=True,
        application_metadata=None,
    )

    similar_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_file_failed_state,
        active_flag=True,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=original_target_id)
    vws_client.wait_for_target_processed(target_id=similar_target_id)

    target_details = vws_client.get_target_record(
        target_id=original_target_id,
    )
    assert target_details.status == TargetStatuses.FAILED

    duplicates = vws_client.get_duplicate_targets(
        target_id=original_target_id,
    )

    assert duplicates == []


def test_order_is_upload_date_then_target_id(
    *,
    backend_capabilities: BackendCapabilities,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
) -> None:
    """The mock returns duplicates ordered by upload date.

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

    for target_id in target_ids:
        vws_client.wait_for_target_processed(target_id=target_id)

    duplicates = vws_client.get_duplicate_targets(
        target_id=target_ids[0],
    )

    assert duplicates == target_ids[1:]
