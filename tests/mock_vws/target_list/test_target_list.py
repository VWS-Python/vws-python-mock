"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.target_list.test_target_list import (
    test_deleted,
    test_includes_targets,
    test_order_is_upload_date_then_target_id,
)

__all__ = [
    "test_deleted",
    "test_includes_targets",
    "test_order_is_upload_date_then_target_id",
]
