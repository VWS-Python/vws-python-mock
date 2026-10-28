"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.add_target.test_target_name import (
    test_deleted_existing_target_name,
    test_existing_target_name,
    test_name_invalid,
    test_name_valid,
)

__all__ = [
    "test_deleted_existing_target_name",
    "test_existing_target_name",
    "test_name_invalid",
    "test_name_valid",
]
