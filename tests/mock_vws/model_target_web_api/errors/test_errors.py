"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.model_target_web_api.errors.test_errors import (
    test_expected_status,
    test_multiple_expected_statuses,
    test_training_allowance_exceeded,
    test_unexpected_status_shows_the_body,
)

__all__ = [
    "test_expected_status",
    "test_multiple_expected_statuses",
    "test_training_allowance_exceeded",
    "test_unexpected_status_shows_the_body",
]
