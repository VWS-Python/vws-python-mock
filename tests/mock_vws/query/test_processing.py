"""Tests for targets in the processing state."""

import io
import uuid

import pytest
from vws import VWS, CloudRecoService
from vws.reports import TargetStatuses


@pytest.mark.parametrize(argnames="active_flag", argvalues=[True, False])
def test_processing(
    *,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
    cloud_reco_client: CloudRecoService,
    active_flag: bool,
) -> None:
    """
    When a target with a matching image is in the processing state
    it is
    not matched.
    """
    target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=high_quality_image,
        active_flag=active_flag,
        application_metadata=None,
    )
    matching_targets = cloud_reco_client.query(image=high_quality_image)
    # We assert that after making a query, the target is in the processing
    # state.
    #
    # There is a race condition here.
    #
    # This is really a check that the test is valid.
    #
    # If the target is no longer in the processing state here, it may be
    # that the test was valid, but the target went into the processed
    # state.
    #
    # If the target is no longer in the processing state here, that is a
    # flaky test that is the test's fault and this must be rethought.
    target_details = vws_client.get_target_record(target_id=target_id)
    assert target_details.status == TargetStatuses.PROCESSING

    assert matching_targets == []
