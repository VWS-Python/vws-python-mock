"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.query.test_truncated_body import (
    test_no_closing_boundary,
    test_no_content_disposition_header,
    test_partial_closing_boundary,
    test_truncated_at_end_of_header,
    test_truncated_image_data,
    test_truncated_in_part_headers,
)

__all__ = [
    "test_no_closing_boundary",
    "test_no_content_disposition_header",
    "test_partial_closing_boundary",
    "test_truncated_at_end_of_header",
    "test_truncated_image_data",
    "test_truncated_in_part_headers",
]
