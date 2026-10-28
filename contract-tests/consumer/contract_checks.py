"""Check the installed suite's adapter and import boundaries."""

import sys

import pytest

__all__ = ["pytest_sessionfinish"]


@pytest.fixture(autouse=True)
def ready(request: pytest.FixtureRequest) -> None:
    """Check that public setup fixtures yield None."""
    for name in ("verify_mock_vuforia", "mock_only_vuforia"):
        if name in request.fixturenames:
            assert request.getfixturevalue(argname=name) is None


def pytest_sessionfinish() -> None:
    """Keep the core repository's tests outside the consumer process."""
    assert not any(name.startswith("tests.mock_vws") for name in sys.modules)
