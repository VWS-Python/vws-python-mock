"""
Tests for the mock of the target list endpoint.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from vws import VWS


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestTargetList:
    """
    Tests for the mock of the target list endpoint at `/targets`.
    """

    @staticmethod
    def test_includes_targets(
        vws_client: VWS,
        target_id: str,
    ) -> None:
        """
        Targets in the database are returned in the list.
        """
        assert vws_client.list_targets() == [target_id]

    @staticmethod
    def test_deleted(
        vws_client: VWS,
        target_id: str,
    ) -> None:
        """
        Deleted targets are not returned in the list.
        """
        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.delete_target(target_id=target_id)
        assert not vws_client.list_targets()


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestInactiveProject:
    """
    Tests for inactive projects.
    """

    @staticmethod
    def test_inactive_project(inactive_vws_client: VWS) -> None:
        """
        The project's active state does not affect the target list.
        """
        # No exception is raised.
        inactive_vws_client.list_targets()
