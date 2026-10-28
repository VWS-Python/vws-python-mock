"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.model_target_web_api.requests.contract.test_content_length import (  # noqa: E501
    test_not_integer,
    test_not_integer_oauth2_token,
    test_too_small,
)

__all__ = [
    "test_not_integer",
    "test_not_integer_oauth2_token",
    "test_too_small",
]
