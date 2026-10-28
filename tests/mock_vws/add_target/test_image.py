"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.add_target.test_image import (
    test_bad_image_format_or_color_space,
    test_corrupted,
    test_decompression_bomb,
    test_image_file_size_too_large,
    test_image_pixel_count_too_large,
    test_image_valid,
    test_invalid_type,
    test_not_base64_encoded_not_processable,
    test_not_base64_encoded_processable,
    test_not_image,
    test_truncated,
)

__all__ = [
    "test_bad_image_format_or_color_space",
    "test_corrupted",
    "test_decompression_bomb",
    "test_image_file_size_too_large",
    "test_image_pixel_count_too_large",
    "test_image_valid",
    "test_invalid_type",
    "test_not_base64_encoded_not_processable",
    "test_not_base64_encoded_processable",
    "test_not_image",
    "test_truncated",
]
