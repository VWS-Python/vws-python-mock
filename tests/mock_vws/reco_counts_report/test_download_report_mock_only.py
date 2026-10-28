"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.reco_counts_report.test_download_report_mock_only import (  # noqa: E501
    test_counts_set_after_first_request,
    test_not_ready,
    test_seeded_recognition_counts,
    test_unknown_report,
)

__all__ = [
    "test_counts_set_after_first_request",
    "test_not_ready",
    "test_seeded_recognition_counts",
    "test_unknown_report",
]
