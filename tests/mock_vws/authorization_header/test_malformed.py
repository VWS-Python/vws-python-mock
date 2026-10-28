"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.authorization_header.test_malformed import (
    test_missing_signature,
    test_one_part_no_space,
    test_one_part_with_space,
)

__all__ = [
    "test_missing_signature",
    "test_one_part_no_space",
    "test_one_part_with_space",
]
