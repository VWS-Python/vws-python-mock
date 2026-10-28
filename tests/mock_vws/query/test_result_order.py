"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.query.test_result_order import (
    test_max_num_results_keeps_the_first_results,
    test_order_is_upload_date_then_target_id,
)

__all__ = [
    "test_max_num_results_keeps_the_first_results",
    "test_order_is_upload_date_then_target_id",
]
