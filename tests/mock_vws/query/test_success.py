"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.query.test_success import (
    test_low_quality_image,
    test_match_exact,
    test_match_similar,
    test_no_results,
    test_not_base64_encoded_processable,
)

__all__ = [
    "test_low_quality_image",
    "test_match_exact",
    "test_match_similar",
    "test_no_results",
    "test_not_base64_encoded_processable",
]
