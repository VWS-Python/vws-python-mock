"""Fixtures scoped to this group of tests."""

import pytest


@pytest.fixture(autouse=True)
def fixture_verify_backend(
    *,
    verify_mock_vuforia: None,
) -> None:
    """Set up the backend for every contract test in this directory."""
    del verify_mock_vuforia
