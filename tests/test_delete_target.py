"""
Tests for helper function for deleting a target from a Vuforia database.
"""

import io

import pytest
from requests import codes

from vws import VWS
from vws.exceptions import TargetStatusProcessing, UnknownTarget

class TestDelete:
    """
    Test for deleting a target.
    """

    def test_target_processing(
        self,
        client: VWS,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        A ``TargetStatusProcessing`` exception is raised if trying to delete a
        target which is processing.
        """
        target_id = client.add_target(
            name='x',
            width=1,
            image=high_quality_image,
        )

        with pytest.raises(TargetStatusProcessing) as exc:
            client.delete_target(target_id=target_id)

        assert exc.value.response.status_code == codes.FORBIDDEN

    def test_delete_target(
        self,
        client: VWS,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        It is possible to delete a target.
        """
        target_id = client.add_target(
            name='x',
            width=1,
            image=high_quality_image,
        )

        client.wait_for_target_processed(target_id=target_id)
        client.delete_target(target_id=target_id)
        with pytest.raises(UnknownTarget):
            client.get_target_record(target_id=target_id)
