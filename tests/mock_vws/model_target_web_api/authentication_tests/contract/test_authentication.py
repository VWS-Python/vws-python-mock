"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.model_target_web_api.authentication_tests.contract.test_authentication import (  # noqa: E501
    test_client_credentials_management,
    test_insufficient_scope,
    test_invalid_oauth2_token_request,
    test_password_grant,
    test_scoped_client_credentials_grant,
)

__all__ = [
    "test_client_credentials_management",
    "test_insufficient_scope",
    "test_invalid_oauth2_token_request",
    "test_password_grant",
    "test_scoped_client_credentials_grant",
]
