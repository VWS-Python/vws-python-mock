"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.query.test_maximum_image_dimensions import (
    test_max_height,
    test_max_pixels,
    test_max_width,
    test_small_file_many_pixels,
)

__all__ = [
    "test_max_height",
    "test_max_pixels",
    "test_max_width",
    "test_small_file_many_pixels",
]
