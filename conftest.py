"""Setup for Sybil."""

import inspect
from doctest import ELLIPSIS

import pytest
from sybil import Sybil
from sybil.parsers.rest import (
    DocTestParser,
    PythonCodeBlockParser,
)
from typeguard import typechecked

from tests.mock_vws.utils.retries import RETRY_EXCEPTIONS

pytest_collect_file = Sybil(
    parsers=[
        DocTestParser(optionflags=ELLIPSIS),
        PythonCodeBlockParser(),
    ],
    patterns=["*.rst", "*.py"],
).pytest()


@pytest.hookimpl(optionalhook=True)
def pytest_set_filtered_exceptions() -> tuple[type[Exception], ...]:
    """
    Return exceptions to retry on.

    This is for ``pytest-retry``.
    The configuration for retries is in ``pyproject.toml``.
    """
    return RETRY_EXCEPTIONS


def pytest_collection_modifyitems(
    items: list[pytest.Item],
) -> None:
    """
    Apply the typeguard decorator to all collected test functions.
    """
    for item in items:
        if isinstance(item, pytest.Function):
            if inspect.ismethod(item.obj):
                # If it's a method, we must handle the `self` argument
                # correctly.
                item.obj = typechecked(item.obj.__func__).__get__(
                    item.parent.obj, item.parent.obj.__class__
                )
            else:
                # If it's a regular function, just apply typechecked
                item.obj = typechecked(item.obj)
