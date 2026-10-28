"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.get_duplicates.test_duplicates import (
    test_duplicates,
    test_duplicates_not_same,
    test_order_is_upload_date_then_target_id,
    test_status,
)

__all__ = [
    "test_duplicates",
    "test_duplicates_not_same",
    "test_order_is_upload_date_then_target_id",
    "test_status",
]
