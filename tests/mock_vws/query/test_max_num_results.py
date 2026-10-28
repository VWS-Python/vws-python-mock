"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.query.test_max_num_results import (
    test_default,
    test_invalid_type,
    test_out_of_range,
    test_valid_accepted,
    test_valid_works,
)

__all__ = [
    "test_default",
    "test_invalid_type",
    "test_out_of_range",
    "test_valid_accepted",
    "test_valid_works",
]
