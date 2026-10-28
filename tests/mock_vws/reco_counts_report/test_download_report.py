"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.reco_counts_report.test_download_report import (
    test_download_report,
    test_expired_url,
    test_missing_query,
    test_second_request_serves_first_report,
    test_shortened_expiry,
)

__all__ = [
    "test_download_report",
    "test_expired_url",
    "test_missing_query",
    "test_second_request_serves_first_report",
    "test_shortened_expiry",
]
