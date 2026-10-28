"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.database_summary.contract import (
    test_database_summary as _contract_tests,
)

test_active_images = _contract_tests.test_active_images
test_deleted = _contract_tests.test_deleted
test_failed_images = _contract_tests.test_failed_images
test_inactive_failed = _contract_tests.test_inactive_failed
test_inactive_images = _contract_tests.test_inactive_images
test_success = _contract_tests.test_success

__all__ = [
    "test_active_images",
    "test_deleted",
    "test_failed_images",
    "test_inactive_failed",
    "test_inactive_images",
    "test_success",
]
