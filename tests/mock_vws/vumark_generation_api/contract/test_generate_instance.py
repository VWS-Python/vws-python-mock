"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.vumark_generation_api.contract.test_generate_instance import (  # noqa: E501
    test_empty_instance_id,
    test_generate_instance_content_type_header,
    test_generate_instance_format,
    test_invalid_accept_header,
    test_non_string_instance_id,
    test_non_vumark_database,
    test_successful_target,
    test_unknown_target,
)

__all__ = [
    "test_empty_instance_id",
    "test_generate_instance_content_type_header",
    "test_generate_instance_format",
    "test_invalid_accept_header",
    "test_non_string_instance_id",
    "test_non_vumark_database",
    "test_successful_target",
    "test_unknown_target",
]
