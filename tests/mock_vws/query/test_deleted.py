"""Tests for matching deleted targets."""

import io
import uuid

from tenacity import Retrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from vws import VWS, CloudRecoService

from tests.mock_vws.utils.retries import TRANSIENT_VWS_EXCEPTIONS


def test_deleted_active(
    *,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
    cloud_reco_client: CloudRecoService,
) -> None:
    """Deleted targets are not matched."""
    target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=None,
    )
    vws_client.wait_for_target_processed(target_id=target_id)
    vws_client.delete_target(target_id=target_id)

    # There is a race condition here.
    # In the real Vuforia, it takes some time for the target deletion
    # to be reflected in the query endpoint.
    #
    # This difference is documented in ``differences-to-vws.rst``.
    #
    # We retry to allow for this difference.
    for attempt in Retrying(
        wait=wait_fixed(wait=0.1),
        stop=stop_after_delay(max_delay=3),
        retry=retry_if_exception_type(
            exception_types=(AssertionError, *TRANSIENT_VWS_EXCEPTIONS),
        ),
        reraise=True,
    ):
        with attempt:
            results = cloud_reco_client.query(image=high_quality_image)
            assert results == []


def test_deleted_inactive(
    *,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
    cloud_reco_client: CloudRecoService,
) -> None:
    """
    No error is returned when querying for an image of recently
    deleted,
    inactive target.
    """
    target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=high_quality_image,
        active_flag=False,
        application_metadata=None,
    )
    vws_client.wait_for_target_processed(target_id=target_id)
    vws_client.delete_target(target_id=target_id)
    results = cloud_reco_client.query(image=high_quality_image)
    assert results == []
