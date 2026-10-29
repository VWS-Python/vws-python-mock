"""Setup and response policies for the real Vuforia test adapter."""

import contextlib
from collections.abc import Generator
from typing import override

import pytest
import requests
from beartype import BeartypeConf, beartype
from requests.exceptions import Timeout as RequestsTimeout
from vws import VWS
from vws.exceptions.vws_exceptions import TargetStatusNotSuccessError
from vws.response import Response

from mock_vws.database import CloudDatabase
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
from vws_mock_contract_tests.utils.retries import (
    RETRY_ON_TARGET_STILL_PROCESSING,
    retry_transient_vws_failures,
    retrying_vws_requests,
)
from vws_mock_test_backends.real_model_target_retries import (
    REAL_MODEL_TARGET_RETRY_POLICY,
)
from vws_mock_test_backends.real_vws_retries import REAL_VWS_RETRYING


@beartype
@retry_transient_vws_failures
def _delete_all_targets(
    *, database_keys: CloudDatabase, base_vws_url: str
) -> None:
    """Delete all targets.

    Args:
        database_keys: The credentials to the Vuforia target database to delete
            all targets in.
        base_vws_url: The base URL of the services API for the backend.
    """
    vws_client = VWS(
        server_access_key=database_keys.server_access_key,
        server_secret_key=database_keys.server_secret_key,
        base_vws_url=base_vws_url,
    )

    targets = vws_client.list_targets()

    for target in targets:
        vws_client.wait_for_target_processed(
            target_id=target,
            # Setting this to 2 is an attempt to avoid 429 Too Many Requests
            # errors.
            seconds_between_requests=2,
        )
        # Even deleted targets can be matched by a query for a few seconds so
        # we change the target to inactive before deleting it.
        with contextlib.suppress(TargetStatusNotSuccessError):
            vws_client.update_target(target_id=target, active_flag=False)
        vws_client.wait_for_target_processed(
            target_id=target, seconds_between_requests=2
        )
        _delete_processed_target(vws_client=vws_client, target_id=target)


@beartype
@RETRY_ON_TARGET_STILL_PROCESSING
def _delete_processed_target(*, vws_client: VWS, target_id: str) -> None:
    """Delete a target which has just been waited on to be processed.

    Args:
        vws_client: A client for the database the target is in.
        target_id: The ID of the target to delete.
    """
    vws_client.delete_target(target_id=target_id)


@beartype
def _handle_real_request_timeout(*, url: str, error: RequestsTimeout) -> None:
    """Skip a shared request which timed out against the real service."""
    del url, error
    pytest.skip(reason="The real Vuforia service timed out.")


@beartype
def enable_real_vuforia(
    *,
    working_database: CloudDatabase,
    inactive_cloud_database: CloudDatabase,
    vumark_vuforia_database: VuMarkCloudDatabase,
    inactive_vumark_database: InactiveVuMarkCloudDatabase,
    monkeypatch: pytest.MonkeyPatch,
    base_vws_url: str,
    base_vwq_url: str,
) -> Generator[None]:
    """Test against the real Vuforia."""
    assert bool(monkeypatch)
    assert bool(inactive_cloud_database)
    assert bool(vumark_vuforia_database)
    assert bool(inactive_vumark_database)
    del base_vwq_url
    with (
        retrying_vws_requests(retrying=REAL_VWS_RETRYING),
        handling_request_timeouts(handler=_handle_real_request_timeout),
    ):
        _delete_all_targets(
            database_keys=working_database, base_vws_url=base_vws_url
        )
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


@beartype(conf=BeartypeConf(is_pep484_tower=True))
class LiveVWS(VWS):
    """A client with a polling default suited to the live contract
    tests.
    """

    # Preserve the optional parameters of the upstream VWS API.
    @override
    def wait_for_target_processed(
        self,
        *,
        target_id: str,
        seconds_between_requests: float = 2.0,
        timeout_seconds: float = 60 * 5,
    ) -> None:
        """Poll at the cleanup interval while retaining explicit overrides."""
        super().wait_for_target_processed(
            target_id=target_id,
            seconds_between_requests=seconds_between_requests,
            timeout_seconds=timeout_seconds,
        )
