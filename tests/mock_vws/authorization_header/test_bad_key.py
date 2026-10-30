"""Compatibility imports for VuMark authentication tests."""

from vws_mock_contract_tests.authorization_header.test_bad_key import (
    test_bad_access_key_services,
    test_bad_secret_key_services,
)

__all__ = ["test_bad_access_key_services", "test_bad_secret_key_services"]
