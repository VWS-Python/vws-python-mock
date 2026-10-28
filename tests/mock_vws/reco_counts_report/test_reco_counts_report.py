"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.reco_counts_report.test_reco_counts_report import (  # noqa: E501
    test_body_is_not_an_object,
    test_current_month_file_name,
    test_database_name_in_path,
    test_malformed_month,
    test_month_out_of_range,
    test_presigned_url_query,
    test_previous_month_file_name,
    test_reco_counts_report,
    test_same_file_in_the_same_hour,
    test_unknown_database_id,
)

__all__ = [
    "test_body_is_not_an_object",
    "test_current_month_file_name",
    "test_database_name_in_path",
    "test_malformed_month",
    "test_month_out_of_range",
    "test_presigned_url_query",
    "test_previous_month_file_name",
    "test_reco_counts_report",
    "test_same_file_in_the_same_hour",
    "test_unknown_database_id",
]
