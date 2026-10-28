"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.utils.request_timeout_policy import (
    handling_request_timeouts,
    propagating_request_timeouts,
)

__all__ = ["handling_request_timeouts", "propagating_request_timeouts"]
