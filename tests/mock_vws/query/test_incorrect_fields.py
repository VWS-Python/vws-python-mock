"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.query.test_incorrect_fields import (
    test_extra_fields,
    test_missing_image,
    test_missing_image_and_extra_fields,
)

__all__ = [
    "test_extra_fields",
    "test_missing_image",
    "test_missing_image_and_extra_fields",
]
