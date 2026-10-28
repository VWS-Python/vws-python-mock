"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.update_target.test_application_metadata import (
    test_base64_encoded,
    test_invalid_type,
    test_metadata_too_large,
    test_not_base64_encoded_not_processable,
    test_not_base64_encoded_processable,
)

__all__ = [
    "test_base64_encoded",
    "test_invalid_type",
    "test_metadata_too_large",
    "test_not_base64_encoded_not_processable",
    "test_not_base64_encoded_processable",
]
