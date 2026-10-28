"""Load shared API fixtures independently of backend adapters."""

import pytest
from beartype import beartype

from vws_mock_contract_tests.utils.retries import TRANSIENT_VWS_EXCEPTIONS

pytest_plugins = [
    "vws_mock_contract_tests.fixtures.prepared_requests",
    "vws_mock_contract_tests.fixtures.model_target_prepared_requests",
    "vws_mock_contract_tests.fixtures.api_contract",
]


@beartype
@pytest.hookimpl(optionalhook=True)
def pytest_set_filtered_exceptions() -> tuple[type[Exception], ...]:
    """Return exceptions to retry on.

    This is for ``pytest-retry``.
    The configuration for retries is in ``pyproject.toml``.

    ``pytest-retry`` treats this as an allowlist: a test which fails
    with anything else is not retried, whatever ``retries`` is set to.
    That is deliberate, because widening it to ``AssertionError`` would
    retry every failing assertion in the suite ten times.

    The consequence is that a test which turns a response into an
    ``AssertionError`` itself, rather than letting an exception out of
    the client, is never retried here. The Model Target Web API tests
    assert on ``requests.Response`` objects and so are in that
    position; they get their own, narrower policy, applied before the
    assertion, in
    :py:mod:`vws_mock_contract_tests.utils.model_target_retries`.
    """
    return TRANSIENT_VWS_EXCEPTIONS
