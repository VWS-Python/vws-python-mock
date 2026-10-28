"""Tests for inactive projects."""

from vws import VWS


def test_inactive_project(inactive_vws_client: VWS) -> None:
    """The project's active state does not affect the target list."""
    # No exception is raised.
    _ = inactive_vws_client.list_targets()
