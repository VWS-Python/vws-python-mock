"""Setup for Sybil."""

from doctest import ELLIPSIS

from sybil import Sybil
from sybil.parsers.rest import (
    DocTestParser,
    PythonCodeBlockParser,
)

pytest_collect_file = Sybil(
    parsers=[
        DocTestParser(optionflags=ELLIPSIS),
        PythonCodeBlockParser(),
    ],
    patterns=["*.rst", "*.py"],
).pytest()


# Load shared fixtures for both core and server tests.
pytest_plugins = [
    "vws_mock_contract_tests.fixtures.plugin",
    "vws_mock_test_backends.vuforia_backends",
]
