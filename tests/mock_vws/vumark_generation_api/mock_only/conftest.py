"""Fixtures scoped to this group of tests."""

import pytest

from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend


@pytest.fixture(autouse=True)
def fixture_verify_backend(
    *,
    mock_only_vuforia: VuforiaBackend,
) -> None:
    """Set up the backend for every contract test in this directory."""
    del mock_only_vuforia
