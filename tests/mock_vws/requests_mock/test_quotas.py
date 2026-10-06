"""Tests for quotas through the `requests-mock` backend.

Tests for request quota exhaustion.

These tests run only against the mock. Deliberately exhausting the request
quota of the real Vuforia test database would make it unusable for the
rest of the verified-fake test suite.
"""

import io
import uuid
from http import HTTPStatus

import pytest
import requests
from vws import VWS
from vws.exceptions.vws_exceptions import (
    AuthenticationFailureError,
    ProjectSuspendedError,
    RequestQuotaReachedError,
    TargetQuotaReachedError,
    TooManyRequestsError,
)
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws import MockVWS
from mock_vws._constants import ResultCodes
from mock_vws._services_validators.exceptions import (
    TooManyRequestsError as TooManyRequestsValidatorError,
)
from mock_vws._services_validators.request_rate_limiter import (
    RequestRateLimiter,
)
from mock_vws.database import CloudDatabase
from mock_vws.request_rate_limits import (
    DOCUMENTED_REQUEST_RATE_LIMITS,
    RateLimitedEndpoint,
    RequestRateLimit,
    RequestRateLimits,
)
from mock_vws.states import States
from tests.mock_vws.utils.assertions import (
    assert_vws_failure,
    assert_vws_too_many_requests,
)


def test_request_quota_available() -> None:
    """A database with request quota accepts VWS requests."""
    database = CloudDatabase(request_quota=1)
    client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    with MockVWS() as mock:
        mock.add_cloud_database(cloud_database=database)
        targets = client.list_targets()

    assert not bool(targets)


def test_request_quota_reached() -> None:
    """A database with no request quota rejects VWS requests."""
    database = CloudDatabase(request_quota=0)
    client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    with MockVWS() as mock:
        mock.add_cloud_database(cloud_database=database)
        with pytest.raises(
            expected_exception=RequestQuotaReachedError,
        ) as exc_info:
            _ = client.list_targets()

    assert_vws_failure(
        response=exc_info.value.response,
        status_code=HTTPStatus.FORBIDDEN,
        result_code=ResultCodes.REQUEST_QUOTA_REACHED,
    )


def test_zero_limit() -> None:
    """A zero request rate limit rejects every VWS request."""
    database = CloudDatabase(requests_per_second_limit=0)
    client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    with MockVWS() as mock:
        mock.add_cloud_database(cloud_database=database)
        with pytest.raises(
            expected_exception=TooManyRequestsError,
        ) as exc_info:
            _ = client.list_targets()

    assert_vws_too_many_requests(response=exc_info.value.response)


def test_limit_applies_before_authentication() -> None:
    """The limit is keyed on the access key and applied before the
    signature is checked, as real Vuforia's Envoy layer does.

    A request with a bad signature uses up the budget, and a request over
    the limit is rejected as rate limited rather than as unauthorized.
    """
    database = CloudDatabase(requests_per_second_limit=1)
    client_with_bad_secret = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=uuid.uuid4().hex,
    )
    client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    with MockVWS() as mock:
        mock.add_cloud_database(cloud_database=database)
        with pytest.raises(expected_exception=AuthenticationFailureError):
            _ = client_with_bad_secret.list_targets()
        with pytest.raises(expected_exception=TooManyRequestsError):
            _ = client_with_bad_secret.list_targets()
        with pytest.raises(expected_exception=TooManyRequestsError):
            _ = client.list_targets()


def test_rolling_window() -> None:
    """Requests are accepted again after the rolling window passes."""
    request_times = iter([10.0, 10.5, 11.0])
    rate_limiter = RequestRateLimiter(
        time_function=request_times.__next__,
    )
    database = CloudDatabase(requests_per_second_limit=1)

    rate_limiter.validate(
        database=database,
        endpoint=RateLimitedEndpoint.OTHER,
    )
    with pytest.raises(expected_exception=TooManyRequestsValidatorError):
        rate_limiter.validate(
            database=database,
            endpoint=RateLimitedEndpoint.OTHER,
        )
    rate_limiter.validate(
        database=database,
        endpoint=RateLimitedEndpoint.OTHER,
    )


def test_limit_applies_to_all_endpoints() -> None:
    """The database-wide limit is shared between all endpoints."""
    request_times = iter([10.0, 10.1])
    rate_limiter = RequestRateLimiter(
        time_function=request_times.__next__,
    )
    database = CloudDatabase(requests_per_second_limit=1)

    rate_limiter.validate(
        database=database,
        endpoint=RateLimitedEndpoint.GET_TARGET,
    )
    with pytest.raises(expected_exception=TooManyRequestsValidatorError):
        rate_limiter.validate(
            database=database,
            endpoint=RateLimitedEndpoint.LIST_TARGETS,
        )


def test_endpoints_are_limited_separately() -> None:
    """Each endpoint group has its own budget of requests."""
    request_times = iter([10.0, 10.1, 10.2])
    rate_limiter = RequestRateLimiter(
        time_function=request_times.__next__,
    )
    database = CloudDatabase(
        request_rate_limits=RequestRateLimits(
            get_target=RequestRateLimit(max_requests=1, window_seconds=1.0),
            get_duplicates=RequestRateLimit(
                max_requests=1, window_seconds=1.0
            ),
        ),
    )

    rate_limiter.validate(
        database=database,
        endpoint=RateLimitedEndpoint.GET_TARGET,
    )
    rate_limiter.validate(
        database=database,
        endpoint=RateLimitedEndpoint.GET_DUPLICATES,
    )
    with pytest.raises(expected_exception=TooManyRequestsValidatorError):
        rate_limiter.validate(
            database=database,
            endpoint=RateLimitedEndpoint.GET_TARGET,
        )


def test_endpoints_without_a_limit_share_the_other_limit() -> None:
    """Endpoints with no limit of their own share the ``other``
    limit.
    """
    request_times = iter([10.0, 10.1, 10.2])
    rate_limiter = RequestRateLimiter(
        time_function=request_times.__next__,
    )
    database = CloudDatabase(
        request_rate_limits=RequestRateLimits(
            other=RequestRateLimit(max_requests=2, window_seconds=1.0),
            get_target=RequestRateLimit(max_requests=1, window_seconds=1.0),
        ),
    )

    rate_limiter.validate(
        database=database,
        endpoint=RateLimitedEndpoint.OTHER,
    )
    # ``GET /targets`` has no limit of its own, so it shares the ``other``
    # limit.
    rate_limiter.validate(
        database=database,
        endpoint=RateLimitedEndpoint.LIST_TARGETS,
    )
    with pytest.raises(expected_exception=TooManyRequestsValidatorError):
        rate_limiter.validate(
            database=database,
            endpoint=RateLimitedEndpoint.OTHER,
        )


def test_windows_longer_than_a_second() -> None:
    """A limit may use a window which is longer than one second."""
    request_times = iter([10.0, 40.0, 71.0])
    rate_limiter = RequestRateLimiter(
        time_function=request_times.__next__,
    )
    database = CloudDatabase(
        request_rate_limits=RequestRateLimits(
            list_targets=RequestRateLimit(
                max_requests=1,
                window_seconds=60.0,
            ),
        ),
    )

    rate_limiter.validate(
        database=database,
        endpoint=RateLimitedEndpoint.LIST_TARGETS,
    )
    with pytest.raises(expected_exception=TooManyRequestsValidatorError):
        rate_limiter.validate(
            database=database,
            endpoint=RateLimitedEndpoint.LIST_TARGETS,
        )
    rate_limiter.validate(
        database=database,
        endpoint=RateLimitedEndpoint.LIST_TARGETS,
    )


def test_rejected_requests_do_not_use_other_budgets() -> None:
    """A request rejected by one limit does not count towards
    another.
    """
    request_times = iter([10.0, 10.1, 10.2])
    rate_limiter = RequestRateLimiter(
        time_function=request_times.__next__,
    )
    database = CloudDatabase(
        requests_per_second_limit=5,
        request_rate_limits=RequestRateLimits(
            list_targets=RequestRateLimit(max_requests=1, window_seconds=1.0)
        ),
    )

    rate_limiter.validate(
        database=database,
        endpoint=RateLimitedEndpoint.LIST_TARGETS,
    )
    with pytest.raises(expected_exception=TooManyRequestsValidatorError):
        rate_limiter.validate(
            database=database,
            endpoint=RateLimitedEndpoint.LIST_TARGETS,
        )
    rate_limiter.validate(
        database=database,
        endpoint=RateLimitedEndpoint.GET_TARGET,
    )


def test_documented_limits() -> None:
    """The documented limits are available to use."""
    database = CloudDatabase(
        request_rate_limits=DOCUMENTED_REQUEST_RATE_LIMITS,
    )
    client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    with MockVWS() as mock:
        mock.add_cloud_database(cloud_database=database)
        # ``GET /targets`` is limited to two requests per minute.
        _targets = client.list_targets()
        _targets = client.list_targets()
        with pytest.raises(
            expected_exception=TooManyRequestsError,
        ) as exc_info:
            _targets = client.list_targets()

        # Other endpoints have their own budgets.
        _summary = client.get_database_summary_report()

    assert_vws_too_many_requests(response=exc_info.value.response)


def test_get_target_and_duplicates_limits(
    *,
    image_file_failed_state: io.BytesIO,
) -> None:
    """``GET /targets/{target_id}`` and ``GET /duplicates/{target_id}``
    have their own limits.
    """
    database = CloudDatabase(
        request_rate_limits=RequestRateLimits(
            get_target=RequestRateLimit(max_requests=2, window_seconds=60.0),
            get_duplicates=RequestRateLimit(
                max_requests=1,
                window_seconds=60.0,
            ),
        ),
    )
    client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    with MockVWS(processing_time_seconds=0) as mock:
        mock.add_cloud_database(cloud_database=database)
        target_id = client.add_target(
            name="example",
            width=1,
            image=image_file_failed_state,
            application_metadata=None,
            active_flag=True,
        )
        _target = client.get_target_record(target_id=target_id)
        _duplicates = client.get_duplicate_targets(target_id=target_id)
        with pytest.raises(expected_exception=TooManyRequestsError):
            _duplicates = client.get_duplicate_targets(target_id=target_id)
        _target = client.get_target_record(target_id=target_id)
        with pytest.raises(expected_exception=TooManyRequestsError):
            _target = client.get_target_record(target_id=target_id)


def test_target_quota_reached(
    *,
    image_file_failed_state: io.BytesIO,
) -> None:
    """A database at its target quota rejects new targets."""
    database = CloudDatabase(target_quota=0)
    client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    with MockVWS() as mock:
        mock.add_cloud_database(cloud_database=database)
        with pytest.raises(
            expected_exception=TargetQuotaReachedError,
        ) as exc_info:
            _ = client.add_target(
                name="example",
                width=1,
                image=image_file_failed_state,
                application_metadata=None,
                active_flag=True,
            )

    assert_vws_failure(
        response=exc_info.value.response,
        status_code=HTTPStatus.FORBIDDEN,
        result_code=ResultCodes.TARGET_QUOTA_REACHED,
    )


def test_project_suspended() -> None:
    """A suspended project rejects VWS requests."""
    database = CloudDatabase(state=States.PROJECT_SUSPENDED)
    client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    with MockVWS() as mock:
        mock.add_cloud_database(cloud_database=database)
        with pytest.raises(
            expected_exception=ProjectSuspendedError,
        ) as exc:
            _ = client.list_targets()

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.FORBIDDEN,
        result_code=ResultCodes.PROJECT_SUSPENDED,
    )


def test_project_has_no_api_access() -> None:
    """A project with no API access rejects VWS requests.

    This does not use ``vws-python`` because that library maps this
    result code by the ``ProjectHasNoAPIAccess`` spelling, which
    Vuforia's result codes table does not use.
    """
    database = CloudDatabase(state=States.PROJECT_HAS_NO_API_ACCESS)
    request_path = "/targets"

    with MockVWS() as mock:
        mock.add_cloud_database(cloud_database=database)
        date = rfc_1123_date()
        auth = authorization_header(
            access_key=database.server_access_key,
            secret_key=database.server_secret_key,
            method="GET",
            content=b"",
            content_type="",
            date=date,
            request_path=request_path,
        )
        response = requests.get(
            url="https://vws.vuforia.com" + request_path,
            headers={
                "Authorization": auth,
                "Date": date,
            },
            timeout=30,
        )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["result_code"] == "ProjectHasNoApiAccess"
