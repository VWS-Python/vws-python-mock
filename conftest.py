"""Setup for Sybil."""

from doctest import ELLIPSIS

import pytest
from sybil import Sybil
from sybil.parsers.rest import (
    DocTestParser,
    PythonCodeBlockParser,
)
from vws.exceptions.custom_exceptions import ServerError
from vws.exceptions.vws_exceptions import TooManyRequests

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
    # This matches the exceptions in ``vuforia_backands.py``
    return (TooManyRequests, ServerError)
