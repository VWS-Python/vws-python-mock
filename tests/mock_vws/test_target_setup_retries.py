"""Regression tests for retries while preparing a successful target."""

import io
import time
from unittest.mock import call, patch

import pytest
from requests.exceptions import ReadTimeout
from tenacity import RetryError
from vws import VWS
from vws.exceptions.vws_exceptions import (
    TooManyRequestsError,
    UnknownTargetError,
)
from vws.reports import TargetRecord, TargetStatusAndRecord, TargetStatuses
from vws.response import Response

from tests.mock_vws.fixtures.api_contract import (
    _add_target_which_processed_successfully,  # pyright: ignore[reportPrivateUsage]
)
from tests.mock_vws.utils.retries import TRANSIENT_VWS_RETRY_ATTEMPTS


def _record(*, status: TargetStatuses) -> TargetStatusAndRecord:
    """Return a record for a target whose processing has finished."""
    return TargetStatusAndRecord(
        status=status,
        target_record=TargetRecord(
            target_id="target",
            active_flag=True,
            name="name",
            width=1,
            tracking_rating=5,
            reco_rating="",
        ),
    )


def _throttle() -> TooManyRequestsError:
    """Return the empty 429 response observed during fixture setup."""
    return TooManyRequestsError(
        response=Response(
            text="",
            url="https://example.com/summary/target",
            status_code=429,
            headers={"x-envoy-ratelimited": "true"},
            request_body=None,
            tell_position=0,
            content=b"",
        )
    )


def _no_sleep(seconds: float) -> None:
    """Keep retry tests independent of wall-clock delays."""
    del seconds


@pytest.fixture(autouse=True)
def fixture_no_sleep(*, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the actual retry decorators without sleeping."""
    monkeypatch.setattr(target=time, name="sleep", value=_no_sleep)


@pytest.fixture(name="client")
def fixture_client() -> VWS:
    """Use synthetic credentials; all client operations are controlled."""
    return VWS(server_access_key="key", server_secret_key="secret")


@pytest.mark.parametrize(argnames="operation", argvalues=["poll", "record"])
@pytest.mark.parametrize(
    argnames="failure", argvalues=["429", "timeout", "unknown"]
)
def test_read_recovery_keeps_target(
    *,
    client: VWS,
    operation: str,
    failure: str,
) -> None:
    """A transient read or visibility failure never repeats the upload."""
    error = {
        "429": _throttle(),
        "timeout": ReadTimeout("timed out"),
        "unknown": UnknownTargetError(response=_throttle().response),
    }[failure]
    record = _record(status=TargetStatuses.SUCCESS)
    with (
        patch.object(
            target=VWS, attribute="add_target", return_value="target"
        ) as add,
        patch.object(
            target=VWS,
            attribute="wait_for_target_processed",
            side_effect=[error, None] if operation == "poll" else None,
        ) as poll,
        patch.object(
            target=VWS,
            attribute="get_target_record",
            side_effect=[error, record] if operation == "record" else None,
            return_value=record,
        ) as read,
        patch.object(target=VWS, attribute="delete_target") as delete,
    ):
        result = _add_target_which_processed_successfully(
            vws_client=client, image=io.BytesIO()
        )
    assert result.target_id == "target"
    add.assert_called_once()
    assert poll.call_args_list == [call(target_id="target")] * 2
    assert read.call_args_list == [call(target_id="target")] * (
        2 if operation == "record" else 1
    )
    delete.assert_not_called()


@pytest.mark.parametrize(argnames="operation", argvalues=["poll", "record"])
@pytest.mark.parametrize(argnames="cleanup_fails", argvalues=[False, True])
def test_read_exhaustion_preserves_error(
    *,
    client: VWS,
    operation: str,
    cleanup_fails: bool,
) -> None:
    """Exhaustion creates no replacement and cleanup cannot hide the error."""
    error = _throttle()
    with (
        patch.object(
            target=VWS, attribute="add_target", return_value="target"
        ) as add,
        patch.object(
            target=VWS,
            attribute="wait_for_target_processed",
            side_effect=error if operation == "poll" else None,
        ) as poll,
        patch.object(
            target=VWS, attribute="get_target_record", side_effect=error
        ) as read,
        patch.object(
            target=VWS,
            attribute="delete_target",
            side_effect=RuntimeError("cleanup failed")
            if cleanup_fails
            else None,
        ) as delete,
        pytest.raises(expected_exception=TooManyRequestsError) as exc,
    ):
        _ = _add_target_which_processed_successfully(
            vws_client=client, image=io.BytesIO()
        )
    assert exc.value is error
    add.assert_called_once()
    assert poll.call_count == TRANSIENT_VWS_RETRY_ATTEMPTS
    assert read.call_count == (
        0 if operation == "poll" else TRANSIENT_VWS_RETRY_ATTEMPTS
    )
    delete.assert_called_once_with(target_id="target")


@pytest.mark.parametrize(argnames="recovers", argvalues=[False, True])
def test_failed_processing_uses_bounded_replacements(
    *, client: VWS, recovers: bool
) -> None:
    """Only an actual failed processing result triggers a new upload."""
    failed = _record(status=TargetStatuses.FAILED)
    success = _record(status=TargetStatuses.SUCCESS)
    with (
        patch.object(
            target=VWS,
            attribute="add_target",
            side_effect=["first", "second", "third"],
        ) as add,
        patch.object(target=VWS, attribute="wait_for_target_processed"),
        patch.object(
            target=VWS,
            attribute="get_target_record",
            side_effect=[failed, success] if recovers else None,
            return_value=failed,
        ),
        patch.object(target=VWS, attribute="delete_target") as delete,
    ):
        if recovers:
            result = _add_target_which_processed_successfully(
                vws_client=client, image=io.BytesIO()
            )
            assert result.target_id == "second"
        else:
            with pytest.raises(expected_exception=RetryError):
                _ = _add_target_which_processed_successfully(
                    vws_client=client, image=io.BytesIO()
                )
    assert add.call_count == (2 if recovers else 3)
    assert delete.call_args_list == (
        [call(target_id="first")]
        if recovers
        else [
            call(target_id="first"),
            call(target_id="second"),
            call(target_id="third"),
        ]
    )
