"""Fixtures scoped to this group of tests."""

import pytest


@pytest.fixture(autouse=True)
def fixture_verify_backend(
    *,
    verify_model_target_mock_vuforia: object,
) -> None:
    """Set up the backend for every contract test in this directory."""
    del verify_model_target_mock_vuforia
