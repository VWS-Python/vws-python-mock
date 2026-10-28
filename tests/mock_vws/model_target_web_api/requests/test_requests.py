"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.model_target_web_api.requests.test_requests import (  # noqa: E501
    test_body_not_json_object,
    test_body_not_utf_8,
    test_invalid_json,
    test_wrong_content_type,
)

__all__ = [
    "test_body_not_json_object",
    "test_body_not_utf_8",
    "test_invalid_json",
    "test_wrong_content_type",
]
