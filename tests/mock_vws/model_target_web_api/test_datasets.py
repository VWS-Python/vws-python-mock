"""Compatibility imports for the packaged contract suite."""

from vws_mock_contract_tests.model_target_web_api.test_datasets import (
    test_advanced_realistic_appearance_not_in_enum,
    test_create_status_and_delete,
    test_create_with_cad_data_blob,
    test_dataset_is_visible_to_the_other_dataset_type,
    test_invalid_state_based_dataset,
    test_oauth2_token_body_not_utf_8,
    test_state_based_dataset,
    test_view_states_are_a_subset,
)

__all__ = [
    "test_advanced_realistic_appearance_not_in_enum",
    "test_create_status_and_delete",
    "test_create_with_cad_data_blob",
    "test_dataset_is_visible_to_the_other_dataset_type",
    "test_invalid_state_based_dataset",
    "test_oauth2_token_body_not_utf_8",
    "test_state_based_dataset",
    "test_view_states_are_a_subset",
]
