"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.database_summary.contract import (
    test_request_usage as _contract_tests,
)

test_bad_target_request = _contract_tests.test_bad_target_request
test_query_request = _contract_tests.test_query_request
test_target_request = _contract_tests.test_target_request

__all__ = [
    "test_bad_target_request",
    "test_query_request",
    "test_target_request",
]
