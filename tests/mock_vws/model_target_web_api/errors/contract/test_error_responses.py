"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.model_target_web_api.errors.contract.test_error_responses import (  # noqa: E501
    test_advanced_model_count_exceeds_limit,
    test_invalid_basic_auth_header,
    test_invalid_dataset_request,
    test_unknown_dataset,
)

__all__ = [
    "test_advanced_model_count_exceeds_limit",
    "test_invalid_basic_auth_header",
    "test_invalid_dataset_request",
    "test_unknown_dataset",
]
