"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.invalid_json.test_invalid_json import (
    test_empty_body,
    test_invalid_json_with_skewed_time,
    test_not_an_object,
    test_not_json,
    test_not_utf_8,
)

__all__ = [
    "test_empty_body",
    "test_invalid_json_with_skewed_time",
    "test_not_an_object",
    "test_not_json",
    "test_not_utf_8",
]
