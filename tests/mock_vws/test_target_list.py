"""
Tests for the mock of the target list endpoint.
"""

import pytest
from vws import VWS


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestTargetList:
    """
    Tests for the mock of the target list endpoint at `/targets`.
    """

    def test_includes_targets(
        self,
        vws_client: VWS,
        target_id: str,
    ) -> None:
        """
        Targets in the database are returned in the list.
        """
        assert vws_client.list_targets() == [target_id]

    def test_deleted(
        self,
        vws_client: VWS,
        target_id: str,
    ) -> None:
        """
        Deleted targets are not returned in the list.
        """
        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.delete_target(target_id=target_id)
        assert vws_client.list_targets() == []


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestInactiveProject:
    """
    Tests for inactive projects.
    """

    def test_inactive_project(
        self,
        inactive_vws_client: VWS,
    ) -> None:
        """
        The project's active state does not affect the target list.
        """
        # No exception is raised.
        inactive_vws_client.list_targets()
