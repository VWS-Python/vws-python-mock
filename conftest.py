"""Setup for Sybil."""

from doctest import ELLIPSIS

import pytest
from beartype import beartype
from sybil import Sybil
from sybil.parsers.rest import (
    DocTestParser,
    PythonCodeBlockParser,
)

from tests.mock_vws.utils.retries import RETRY_EXCEPTIONS


@beartype
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply the beartype decorator to all collected test functions."""
    for item in items:
        if isinstance(item, pytest.Function):
            item.obj = beartype(obj=item.obj)


pytest_collect_file = Sybil(
    parsers=[
        DocTestParser(optionflags=ELLIPSIS),
        PythonCodeBlockParser(),
    ],
    patterns=["*.rst", "*.py"],
).pytest()


@beartype
@pytest.hookimpl(optionalhook=True)
def pytest_set_filtered_exceptions() -> tuple[type[Exception], ...]:
    """Return exceptions to retry on.

    This is for ``pytest-retry``.
    The configuration for retries is in ``pyproject.toml``.
    """
    return RETRY_EXCEPTIONS
