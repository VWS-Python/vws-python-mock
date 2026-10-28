"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.model_target_web_api.authentication_tests.contract.test_authorization_header import (  # noqa: E501
    test_invalid_bearer_token,
    test_missing,
)

__all__ = ["test_invalid_bearer_token", "test_missing"]
