"""Real-service retry timing and adapter-policy isolation."""

import datetime
import random
from unittest.mock import patch

import pytest
from freezegun import freeze_time
from requests.exceptions import ReadTimeout
from tenacity import RetryCallState
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_none
from vws.exceptions.vws_exceptions import (
    TooManyRequestsError,
    UnknownTargetError,
)
from vws.response import Response

from mock_vws.database import CloudDatabase
from tests.mock_vws.fixtures.credentials import (
    InactiveVuMarkCloudDatabase,
    VuMarkCloudDatabase,
)
from tests.mock_vws.fixtures.real_vws_retries import (
    REAL_VWS_RETRYING,
    RETRY_BUDGET_SECONDS,
    wait_for_real_vws,
)
from tests.mock_vws.fixtures.vuforia_backends import (
    _enable_use_real_vuforia,  # pyright: ignore[reportPrivateUsage]
)
from tests.mock_vws.utils.retries import (
    TRANSIENT_VWS_RETRY_ATTEMPTS,
    retry_transient_vws_failures,
    retrying_vws_requests,
)


def _throttle(*, headers: dict[str, str]) -> TooManyRequestsError:
    """Build a throttle carrying the original response details."""
    return TooManyRequestsError(
        response=Response(
            text="",
            url="https://example.com/summary/target",
            status_code=429,
            headers={"x-envoy-ratelimited": "true", **headers},
            request_body=None,
            tell_position=0,
            content=b"",
        )
    )


def _state(*, error: Exception, attempt: int) -> RetryCallState:
    """Build the failed attempt supplied to a Tenacity wait function."""
    state = RetryCallState(
        retry_object=REAL_VWS_RETRYING, fn=None, args=(), kwargs={}
    )
    state.attempt_number = attempt
    state.set_exception(exc_info=(type(error), error, None))
    return state


@pytest.mark.parametrize(
    argnames=("header", "expected"),
    argvalues=[
        ("7", 7.0),
        (" 7 ", 7.0),
        ("0", 0.0),
        ("00000000000000000000", 0.0),
        ("Fri, 16 Oct 2026 12:00:07 GMT", 7.0),
        ("Fri, 16 Oct 2026 11:00:00 GMT", 0.0),
        ("99999999999999999999999999999", float("inf")),
    ],
)
def test_retry_after(*, header: str, expected: float) -> None:
    """Both header forms control the delay, including dates in the
    past.
    """
    state = _state(error=_throttle(headers={"rEtRy-AfTeR": header}), attempt=1)
    with freeze_time(time_to_freeze="2026-10-16 12:00:00"):
        assert wait_for_real_vws(retry_state=state) == expected


@pytest.mark.parametrize(
    argnames="header",
    argvalues=["", "invalid", "-1", "1.5", "NaN", "Fri, 16 Oct 2026 12:00:07"],
)
def test_malformed_header_uses_fallback(*, header: str) -> None:
    """Malformed delay headers fall back to jitter."""
    expected_delay = 0.5
    state = _state(error=_throttle(headers={"Retry-After": header}), attempt=1)
    with patch.object(
        target=random, attribute="uniform", return_value=expected_delay
    ):
        assert wait_for_real_vws(retry_state=state) == expected_delay


@pytest.mark.parametrize(
    argnames=("attempt", "upper"),
    argvalues=[(1, 1), (2, 2), (5, 16), (6, 30), (10, 30)],
)
@pytest.mark.parametrize(argnames="throttle", argvalues=[True, False])
def test_fallback_jitter_bounds(
    *, attempt: int, upper: int, throttle: bool
) -> None:
    """Missing delay headers and transport errors use exponential
    jitter.
    """
    error = _throttle(headers={}) if throttle else ReadTimeout("timeout")
    expected_delay = 0.5
    state = _state(error=error, attempt=attempt)
    with patch.object(
        target=random, attribute="uniform", return_value=expected_delay
    ) as uniform:
        assert wait_for_real_vws(retry_state=state) == expected_delay
    uniform.assert_called_once_with(0, upper)


def test_delay_larger_than_budget_surfaces_original_response() -> None:
    """Do not truncate a server delay to squeeze in another attempt."""
    error = _throttle(
        headers={"Retry-After": str(object=RETRY_BUDGET_SECONDS + 1)}
    )
    with (
        patch.object(target=REAL_VWS_RETRYING, attribute="sleep") as sleep,
        pytest.raises(expected_exception=TooManyRequestsError) as exc,
    ):
        _ = REAL_VWS_RETRYING(lambda: _raise(error=error))
    assert exc.value is error
    assert exc.value.response is error.response
    sleep.assert_not_called()


def _raise(*, error: Exception) -> None:
    """Raise the supplied exception.

    Raises:
        Exception: The exact supplied exception.
    """
    raise error


def test_deadline_accounts_for_elapsed_time() -> None:
    """No further attempt is scheduled when the delay no longer fits."""
    error = _throttle(headers={"Retry-After": "50"})
    sleeps: list[float] = []
    attempts = 0
    with freeze_time(time_to_freeze="2026-10-16 12:00:00") as frozen:

        def sleep(seconds: float) -> None:
            """Advance the fake clock instead of actually sleeping."""
            sleeps.append(seconds)
            frozen.tick(delta=datetime.timedelta(seconds=seconds))

        def send() -> None:
            """Spend part of the deadline waiting for a server
            response.
            """
            nonlocal attempts
            attempts += 1
            frozen.tick(delta=datetime.timedelta(seconds=10))
            raise error

        with pytest.raises(expected_exception=TooManyRequestsError):
            _ = REAL_VWS_RETRYING.copy(sleep=sleep)(send)
    assert attempts == len(sleeps) + 1
    assert sleeps == [50.0]


def test_nested_operations_share_attempt_budget(
    *, caplog: pytest.LogCaptureFixture
) -> None:
    """Nested decorated helpers do not each start a ten-attempt loop."""
    attempts = 0
    error = _throttle(headers={"Authorization": "secret"})

    @retry_transient_vws_failures
    def inner() -> None:
        """Always encounter a throttle."""
        nonlocal attempts
        attempts += 1
        raise error

    @retry_transient_vws_failures
    def outer() -> None:
        """Call another decorated operation."""
        inner()

    with (
        retrying_vws_requests(
            retrying=REAL_VWS_RETRYING.copy(wait=wait_none())
        ),
        pytest.raises(expected_exception=TooManyRequestsError) as exc,
    ):
        outer()
    assert exc.value is error
    assert attempts == TRANSIENT_VWS_RETRY_ATTEMPTS
    assert len(caplog.records) == TRANSIENT_VWS_RETRY_ATTEMPTS - 1
    assert "TooManyRequestsError" in caplog.text
    assert "429" in caplog.text
    assert "delay" in caplog.text
    assert "secret" not in caplog.text


def test_scopes_restore_policy_after_exception() -> None:
    """Nested scopes restore the preceding policy after a failure."""
    attempts = 0
    checkpoints: list[int] = []
    error = ReadTimeout("timeout")

    @retry_transient_vws_failures
    def send() -> None:
        """Count and fail each call."""
        nonlocal attempts
        attempts += 1
        raise error

    with retrying_vws_requests(
        retrying=REAL_VWS_RETRYING.copy(
            wait=wait_none(),
            stop=stop_after_attempt(max_attempt_number=2),
        )
    ):
        with (
            retrying_vws_requests(
                retrying=REAL_VWS_RETRYING.copy(
                    wait=wait_none(),
                    stop=stop_after_attempt(max_attempt_number=1),
                )
            ),
            pytest.raises(expected_exception=ReadTimeout),
        ):
            send()
        checkpoints.append(attempts)
        with pytest.raises(expected_exception=ReadTimeout):
            send()
        checkpoints.append(attempts)
    with pytest.raises(expected_exception=ReadTimeout):
        send()
    checkpoints.append(attempts)
    assert checkpoints == [1, 3, 4]


def test_unknown_target_is_not_globally_transient() -> None:
    """Only the known-target visibility helper may retry UnknownTarget."""
    error = UnknownTargetError(response=_throttle(headers={}).response)
    with (
        patch.object(target=REAL_VWS_RETRYING, attribute="sleep") as sleep,
        pytest.raises(expected_exception=UnknownTargetError),
    ):
        _ = REAL_VWS_RETRYING(lambda: _raise(error=error))
    sleep.assert_not_called()


def test_real_adapter_installs_policy_before_cleanup(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real adapter enables retries for setup and restores them on
    exit.
    """
    attempts = 0
    checkpoints: list[int] = []
    error = ReadTimeout("timeout")

    @retry_transient_vws_failures
    def operation() -> None:
        """Recover a single transient error under the installed policy."""
        nonlocal attempts
        attempts += 1
        if attempts % 2:
            raise error

    def cleanup(*, database_keys: CloudDatabase, base_vws_url: str) -> None:
        """Check policy installation during the adapter's initial
        cleanup.
        """
        del database_keys, base_vws_url
        operation()

    cloud = CloudDatabase()
    vumark = VuMarkCloudDatabase(
        target_manager_database_name="name",
        server_access_key="key",
        server_secret_key="secret",
        target_id="target",
        processing_target_id="processing",
    )
    inactive = InactiveVuMarkCloudDatabase(
        target_manager_database_name="inactive",
        server_access_key="key",
        server_secret_key="secret",
    )
    with (
        patch(
            target="tests.mock_vws.fixtures.vuforia_backends._delete_all_targets",
            side_effect=cleanup,
        ),
        patch.object(
            target=REAL_VWS_RETRYING, attribute="wait", new=wait_none()
        ),
    ):
        setup = _enable_use_real_vuforia(
            working_database=cloud,
            inactive_cloud_database=cloud,
            vumark_vuforia_database=vumark,
            inactive_vumark_database=inactive,
            monkeypatch=monkeypatch,
            base_vws_url="https://example.com",
            base_vwq_url="https://example.com",
        )
        assert next(setup) is None
        checkpoints.append(attempts)
        operation()
        checkpoints.append(attempts)
        setup.close()
    with pytest.raises(expected_exception=ReadTimeout):
        operation()
    checkpoints.append(attempts)
    assert checkpoints == [2, 4, 5]
