"""Tests for quotas and thresholds."""

from vws import VWS


def test_quotas(vws_client: VWS) -> None:
    """Quotas are included in the database summary.

    These match the quotas given for a free license.
    """
    report = vws_client.get_database_summary_report()
    expected_target_quota = 1000
    expected_request_quota = 100000
    expected_reco_threshold = 1000
    assert report.target_quota == expected_target_quota
    assert report.request_quota == expected_request_quota
    assert report.reco_threshold == expected_reco_threshold
