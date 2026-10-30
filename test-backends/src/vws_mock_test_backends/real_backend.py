"""Setup and response policies for the real Vuforia test adapter."""

from collections.abc import Generator

import pytest
import requests
from beartype import beartype
from requests.exceptions import Timeout as RequestsTimeout
from vws.response import Response

from vws_mock_contract_tests.fixtures.credentials import (
    InactiveVuMarkCloudDatabase,
    VuMarkCloudDatabase,
)
from vws_mock_contract_tests.utils.model_target_response_policy import (
    handling_unexpected_model_target_responses,
)
from vws_mock_contract_tests.utils.model_target_retries import (
    retrying_model_target_requests,
)
from vws_mock_contract_tests.utils.request_timeout_policy import (
    handling_request_timeouts,
)
from vws_mock_test_backends.real_model_target_retries import (
    REAL_MODEL_TARGET_RETRY_POLICY,
)


@beartype
def _handle_real_request_timeout(*, url: str, error: RequestsTimeout) -> None:
    """Skip a shared request which timed out against the real service."""
    del url, error
    pytest.skip(reason="The real Vuforia service timed out.")


@beartype
def enable_real_vuforia(
    *,
    vumark_vuforia_database: VuMarkCloudDatabase,
    inactive_vumark_database: InactiveVuMarkCloudDatabase,
    monkeypatch: pytest.MonkeyPatch,
    base_vws_url: str,
) -> Generator[None]:
    """Test against the real Vuforia."""
    del base_vws_url
    assert bool(monkeypatch)
    assert bool(vumark_vuforia_database)
    assert bool(inactive_vumark_database)
    with (
        handling_request_timeouts(handler=_handle_real_request_timeout),
    ):
        yield


@beartype
def _handle_real_model_target_response(
    *,
    response: Response | requests.Response,
) -> None:
    """Skip an unexpected rejection by the shared real account's allowance."""
    if "TRAINING_ALLOWANCE_EXCEEDED" in response.text:
        pytest.skip(
            reason=(
                "The Vuforia account is out of Model Target training "
                "allowance - this is not a failure of the code under test."
            ),
        )


@beartype
def enable_real_model_targets(
    *,
    monkeypatch: pytest.MonkeyPatch,
    base_vws_url: str,
) -> Generator[None]:
    """Test against the real Model Target Web API.

    Safe requests are retried past a transient gateway failure, which
    the load balancer in front of the real Model Target Web API
    occasionally returns for a request which is not at fault.
    """
    del base_vws_url
    assert bool(monkeypatch)
    with (
        retrying_model_target_requests(
            retrying=REAL_MODEL_TARGET_RETRY_POLICY,
        ),
        handling_request_timeouts(handler=_handle_real_request_timeout),
        handling_unexpected_model_target_responses(
            handler=_handle_real_model_target_response,
        ),
    ):
        yield
