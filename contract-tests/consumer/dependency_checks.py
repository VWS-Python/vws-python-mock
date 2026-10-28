"""Check that collecting the shared suite needs no implementation."""

import importlib.util
import sys

__all__ = ["pytest_sessionstart"]


def pytest_sessionstart() -> None:
    """Reject implementation dependencies before collection begins."""
    assert importlib.util.find_spec(name="mock_vws") is None
    assert importlib.util.find_spec(name="flask") is None
    assert not any(name.startswith("tests.mock_vws") for name in sys.modules)
