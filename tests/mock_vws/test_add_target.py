"""
Tests for the mock of the add target endpoint.
"""

from __future__ import annotations

import sys

import pytest


@pytest.mark.parametrize(
    "arg",
    [
        123,  # correct type int
        456.789,  # wrong type float, mypy plugin to complain
    ],
)
def test_foo(
    arg: int,  # plugin reads `int` annotation here
) -> None:
    """
    Stub test.
    """
    sys.stdout.write(str(arg))
