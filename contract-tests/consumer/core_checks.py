"""Check that the core wheel works without the Flask server extra."""

import importlib.util

from mock_vws import MockVWS

__all__ = ["pytest_sessionstart"]


def pytest_sessionstart() -> None:
    """Import and enter the core mock without a Flask installation."""
    assert importlib.util.find_spec(name="flask") is None
    with MockVWS():
        pass
