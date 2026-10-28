"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.database_summary.contract import (
    test_inactive_project as _contract_tests,
)

test_inactive_project = _contract_tests.test_inactive_project

__all__ = ["test_inactive_project"]
