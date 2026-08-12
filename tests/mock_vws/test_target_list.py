"""Tests for the mock of the target list endpoint."""

import io
import uuid

import pytest
from vws import VWS

from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestTargetList:
    """Tests for the mock of the target list endpoint at `/targets`."""

    @staticmethod
    def test_includes_targets(
        *,
        vws_client: VWS,
        unprocessed_target_id: str,
    ) -> None:
        """Targets in the database are returned in the list."""
        assert vws_client.list_targets() == [unprocessed_target_id]

    @staticmethod
    def test_deleted(
        *,
        vws_client: VWS,
        target_id: str,
    ) -> None:
        """Deleted targets are not returned in the list."""
        vws_client.delete_target(target_id=target_id)
        assert not vws_client.list_targets()

    @staticmethod
    def test_order_is_upload_date_then_target_id(
        *,
        verify_mock_vuforia: VuforiaBackend,
        high_quality_image: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """The mock returns targets ordered by upload date.

        The real Vuforia Web Services do not document an order, so we do
        not verify this against them.
        """
        if verify_mock_vuforia == VuforiaBackend.REAL:
            pytest.skip(reason="The real Vuforia does not document an order.")

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


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestInactiveProject:
    """Tests for inactive projects."""

    @staticmethod
    def test_inactive_project(inactive_vws_client: VWS) -> None:
        """The project's active state does not affect the target list."""
        # No exception is raised.
        inactive_vws_client.list_targets()
