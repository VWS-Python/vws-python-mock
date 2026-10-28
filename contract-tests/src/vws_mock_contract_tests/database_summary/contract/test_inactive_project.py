"""Tests for inactive projects."""

from vws import VWS


def test_inactive_project(
    inactive_vws_client: VWS,
) -> None:
    """The project's active state does not affect the database summary."""
    _ = inactive_vws_client.get_database_summary_report()
