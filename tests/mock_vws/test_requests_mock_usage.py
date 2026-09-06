"""Tests for the usage of the mock for ``requests``."""

import dataclasses
import datetime
import email.utils
import io
import json
import socket
import uuid
import zipfile
from http import HTTPStatus
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
import httpx2
import pytest
import requests
from beartype import beartype
from freezegun import freeze_time
from PIL import Image
from vws import VWS, CloudRecoService, VuMarkService
from vws.exceptions.vws_exceptions import (
    ProjectSuspendedError,
    RequestQuotaReachedError,
    TargetQuotaReachedError,
    TooManyRequestsError,
)
from vws.reports import TargetStatuses
from vws.transports import HTTPXTransport
from vws.vumark_accept import VuMarkAccept
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws import MissingSchemeError, MockVWS
from mock_vws._constants import ResultCodes
from mock_vws._services_validators.exceptions import (
    TooManyRequestsError as TooManyRequestsValidatorError,
)
from mock_vws._services_validators.request_rate_validators import (
    RequestRateLimiter,
)
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.database_type import DatabaseType
from mock_vws.image_matchers import ExactMatcher, StructuralSimilarityMatcher
from mock_vws.request_rate_limits import (
    DOCUMENTED_REQUEST_RATE_LIMITS,
    RateLimitedEndpoint,
    RequestRateLimit,
    RequestRateLimits,
)
from mock_vws.states import States
from mock_vws.target import ImageTarget, VuMarkTarget
from mock_vws.target_raters import HardcodedTargetTrackingRater
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import assert_vws_failure
from tests.mock_vws.utils.usage_test_helpers import (
    processing_time_seconds,
)

_MODEL_TARGET_AUTHORIZATION = (
    "Bearer eyJhbGciOiJtb2NrIn0."
    "eyJzY29wZSI6Im1vZGVsdGFyZ2V0cy5hbGwifQ."
    "c2lnbmF0dXJl"
)
_MODEL_TARGET_DATASET_REQUEST = {
    "name": "dataset-name",
    "targetSdk": "10.18",
    "models": [
        {
            "name": "model-name",
            "cadDataUrl": "https://example.com/model.glb",
            "views": [
                {
                    "name": "view-name",
                    "guideViewPosition": {
                        "translation": [0, 0, 5],
                        "rotation": [0, 0, 0, 1],
                    },
                },
            ],
        },
    ],
}


@beartype
def _not_exact_matcher(
    first_image_content: bytes,
    second_image_content: bytes,
) -> float | None:
    """A matcher which matches images which are not the same."""
    if first_image_content != second_image_content:
        return 1.0
    return None


@beartype
def _image_length_matcher(
    first_image_content: bytes,
    second_image_content: bytes,
) -> float | None:
    """A matcher which matches every image.

    Images whose contents are closer in length get a higher score.
    """
    return float(-abs(len(first_image_content) - len(second_image_content)))


@beartype
def _bool_matcher(
    first_image_content: bytes,
    second_image_content: bytes,
) -> bool:
    """A matcher of the kind which was supported before matchers gave
    scores.
    """
    return first_image_content == second_image_content


@beartype
def _unused_local_url() -> str:
    """Return a URL for a local address with nothing listening on it."""
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://localhost:{port}"


@beartype
def request_unmocked_address() -> None:
    """Make a request, using `requests` to an unmocked, free local address.

    Raises:
        requests.exceptions.ConnectionError: This is expected as there is
            nothing to connect to.
        requests.exceptions.ConnectionError: This request is being made in the
            context of a ``responses`` mock which does not mock local
            addresses.
    """
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    requests.get(url=f"http://localhost:{port}", timeout=30)


@beartype
def request_mocked_address() -> None:
    """
    Make a request, using `requests` to an address that is mocked by
    `MockVWS`.
    """
    requests.get(
        url="https://vws.vuforia.com/summary",
        headers={
            "Date": rfc_1123_date(),
            "Authorization": "bad_auth_token",
        },
        data=b"",
        timeout=30,
    )


class TestRealHTTP:
    """Tests for making requests to mocked and unmocked addresses."""

    @staticmethod
    def test_default() -> None:
        """
        By default, the mock stops any requests made with `requests` to
        non-
        Vuforia addresses, but not to mocked Vuforia endpoints.
        """
        with MockVWS():
            with pytest.raises(
                expected_exception=requests.exceptions.ConnectionError
            ):
                request_unmocked_address()

            # No exception is raised when making a request to a mocked
            # endpoint.
            request_mocked_address()

        # The mocking stops when the context manager stops.
        with pytest.raises(
            expected_exception=requests.exceptions.ConnectionError
        ):
            request_unmocked_address()

    @staticmethod
    def test_real_http() -> None:
        """
        When the `real_http` parameter given to the context manager is
        set to
        `True`, requests made to unmocked addresses are not stopped.
        """
        with (
            MockVWS(real_http=True),
            pytest.raises(
                expected_exception=requests.exceptions.ConnectionError
            ),
        ):
            request_unmocked_address()


class TestResponseDelay:
    """Tests for the response delay feature."""

    @staticmethod
    def test_default_no_delay() -> None:
        """By default, there is no response delay."""
        with MockVWS():
            # With a very short timeout, the request should still succeed
            # because there is no delay
            response = requests.get(
                url="https://vws.vuforia.com/summary",
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                data=b"",
                timeout=0.5,
            )
            # We just care that no timeout occurred, not the response content
            assert response.status_code is not None

    @staticmethod
    def test_delay_causes_timeout() -> None:
        """
        When response_delay_seconds is set higher than the client
        timeout,
        a Timeout exception is raised.
        """
        with (
            MockVWS(response_delay_seconds=0.5),
            pytest.raises(expected_exception=requests.exceptions.Timeout),
        ):
            requests.get(
                url="https://vws.vuforia.com/summary",
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                data=b"",
                timeout=0.1,
            )

    @staticmethod
    def test_delay_allows_completion() -> None:
        """
        When response_delay_seconds is set lower than the client
        timeout,
        the request completes successfully.
        """
        with MockVWS(response_delay_seconds=0.1):
            # This should succeed because timeout > delay
            response = requests.get(
                url="https://vws.vuforia.com/summary",
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                data=b"",
                timeout=2.0,
            )
            assert response.status_code is not None

    @staticmethod
    def test_delay_without_timeout() -> None:
        """A request without a timeout waits for the configured delay."""
        calls: list[float] = []
        with MockVWS(
            response_delay_seconds=0.1,
            sleep_fn=calls.append,
        ):
            # Omitting the timeout is the behavior under test.
            # pylint: disable-next=missing-timeout
            response = requests.get(  # noqa: S113
                url="https://vws.vuforia.com/summary",
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                data=b"",
            )

        assert response.status_code is not None
        assert calls == [0.1]

    @staticmethod
    def test_delay_with_tuple_timeout() -> None:
        """
        The response delay works correctly with tuple timeouts
        (connect_timeout, read_timeout).
        """
        with (
            MockVWS(response_delay_seconds=0.5),
            pytest.raises(expected_exception=requests.exceptions.Timeout),
        ):
            # Tuple timeout: (connect_timeout, read_timeout)
            # The read timeout (0.1) is less than the delay (0.5)
            requests.get(
                url="https://vws.vuforia.com/summary",
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                data=b"",
                timeout=(5.0, 0.1),
            )

    @staticmethod
    def test_custom_sleep_fn_called_on_delay() -> None:
        """
        When a custom ``sleep_fn`` is provided, it is called instead of
        ``time.sleep`` for the non-timeout delay path.
        """
        calls: list[float] = []
        with MockVWS(
            response_delay_seconds=5.0,
            sleep_fn=calls.append,
        ):
            requests.get(
                url="https://vws.vuforia.com/summary",
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                data=b"",
                timeout=30,
            )
        assert calls == [5.0]

    @staticmethod
    def test_custom_sleep_fn_called_on_timeout() -> None:
        """
        When a custom ``sleep_fn`` is provided, it is called instead of
        ``time.sleep`` for the timeout path.
        """
        calls: list[float] = []
        with (
            MockVWS(
                response_delay_seconds=5.0,
                sleep_fn=calls.append,
            ),
            pytest.raises(expected_exception=requests.exceptions.Timeout),
        ):
            requests.get(
                url="https://vws.vuforia.com/summary",
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                data=b"",
                timeout=1.0,
            )
        # sleep_fn should have been called with the effective timeout
        assert calls == [1.0]


class TestProcessingTime:
    """Tests for the time taken to process targets in the mock."""

    # There is a race condition in this test type - if tests start to
    # fail, consider increasing the leeway.
    LEEWAY = 1.0

    def test_default(self, image_file_failed_state: io.BytesIO) -> None:
        """By default, targets in the mock takes 2 seconds to be processed."""
        database = CloudDatabase()
        with MockVWS() as mock:
            mock.add_cloud_database(cloud_database=database)
            time_taken = processing_time_seconds(
                vuforia_database=database,
                image=image_file_failed_state,
            )

        expected = 2
        assert expected - self.LEEWAY < time_taken < expected + self.LEEWAY

    def test_custom(self, image_file_failed_state: io.BytesIO) -> None:
        """It is possible to set a custom processing time."""
        database = CloudDatabase()
        seconds = 5
        with MockVWS(processing_time_seconds=seconds) as mock:
            mock.add_cloud_database(cloud_database=database)
            time_taken = processing_time_seconds(
                vuforia_database=database,
                image=image_file_failed_state,
            )

        expected = seconds
        assert expected - self.LEEWAY < time_taken < expected + self.LEEWAY


class TestDatabaseName:
    """Tests for the database name."""

    @staticmethod
    def test_default() -> None:
        """By default, the database has a random name."""
        database_details = CloudDatabase()
        other_database_details = CloudDatabase()
        assert (
            database_details.database_name
            != other_database_details.database_name
        )

    @staticmethod
    def test_custom_name() -> None:
        """It is possible to set a custom database name."""
        database_details = CloudDatabase(database_name="foo")
        assert database_details.database_name == "foo"


class TestRequestQuota:
    """Tests for request quota exhaustion.

    These tests run only against the mock. Deliberately exhausting the request
    quota of the real Vuforia test database would make it unusable for the
    rest of the verified-fake test suite.
    """

    @staticmethod
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

        assert not targets

    @staticmethod
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
                client.list_targets()

        assert_vws_failure(
            response=exc_info.value.response,
            status_code=HTTPStatus.FORBIDDEN,
            result_code=ResultCodes.REQUEST_QUOTA_REACHED,
        )


class TestRequestRateLimit:
    """Tests for configurable per-second VWS request limits."""

    @staticmethod
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
                client.list_targets()

        assert_vws_failure(
            response=exc_info.value.response,
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            result_code=ResultCodes.TOO_MANY_REQUESTS,
        )

    @staticmethod
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

    @staticmethod
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


class TestPerEndpointRequestRateLimits:
    """Tests for per-endpoint VWS request rate limits."""

    @staticmethod
    def test_endpoints_are_limited_separately() -> None:
        """Each endpoint group has its own budget of requests."""
        request_times = iter([10.0, 10.1, 10.2])
        rate_limiter = RequestRateLimiter(
            time_function=request_times.__next__,
        )
        database = CloudDatabase(
            request_rate_limits=RequestRateLimits(
                get_target=RequestRateLimit(
                    max_requests=1, window_seconds=1.0
                ),
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

    @staticmethod
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
                get_target=RequestRateLimit(
                    max_requests=1, window_seconds=1.0
                ),
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

    @staticmethod
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

    @staticmethod
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
                list_targets=RequestRateLimit(
                    max_requests=1, window_seconds=1.0
                )
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

    @staticmethod
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
            # ``GET /targets`` is limited to one request per minute.
            client.list_targets()
            with pytest.raises(
                expected_exception=TooManyRequestsError,
            ) as exc_info:
                client.list_targets()

            # Other endpoints have their own budgets.
            client.get_database_summary_report()

        assert_vws_failure(
            response=exc_info.value.response,
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            result_code=ResultCodes.TOO_MANY_REQUESTS,
        )

    @staticmethod
    def test_get_target_and_duplicates_limits(
        *,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """``GET /targets/{target_id}`` and ``GET /duplicates/{target_id}``
        have their own limits.
        """
        database = CloudDatabase(
            request_rate_limits=RequestRateLimits(
                get_target=RequestRateLimit(
                    max_requests=2, window_seconds=60.0
                ),
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
            client.get_target_record(target_id=target_id)
            client.get_duplicate_targets(target_id=target_id)
            with pytest.raises(expected_exception=TooManyRequestsError):
                client.get_duplicate_targets(target_id=target_id)
            client.get_target_record(target_id=target_id)
            with pytest.raises(expected_exception=TooManyRequestsError):
                client.get_target_record(target_id=target_id)


class TestAdditionalResultCodes:
    """Tests for configurable, mock-only VWS result codes."""

    @staticmethod
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
                client.add_target(
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

    @staticmethod
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
                client.list_targets()

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.FORBIDDEN,
            result_code=ResultCodes.PROJECT_SUSPENDED,
        )

    @staticmethod
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


class TestCustomBaseURLs:
    """Tests for using custom base URLs."""

    @staticmethod
    def test_custom_base_vws_url() -> None:
        """It is possible to use a custom base VWS URL."""
        with MockVWS(
            base_vws_url="https://vuforia.vws.example.com",
            real_http=False,
        ):
            with pytest.raises(
                expected_exception=requests.exceptions.ConnectionError
            ):
                requests.get(url="https://vws.vuforia.com/summary", timeout=30)

            requests.get(
                url="https://vuforia.vws.example.com/summary",
                timeout=30,
            )
            requests.post(
                url="https://cloudreco.vuforia.com/v1/query",
                timeout=30,
            )

    @staticmethod
    def test_custom_base_vwq_url() -> None:
        """It is possible to use a custom base cloud recognition URL."""
        with MockVWS(
            base_vwq_url="https://vuforia.vwq.example.com",
            real_http=False,
        ):
            with pytest.raises(
                expected_exception=requests.exceptions.ConnectionError
            ):
                requests.post(
                    url="https://cloudreco.vuforia.com/v1/query",
                    timeout=30,
                )

            requests.post(
                url="https://vuforia.vwq.example.com/v1/query",
                timeout=30,
            )
            requests.get(
                url="https://vws.vuforia.com/summary",
                timeout=30,
            )

    @staticmethod
    def test_custom_base_vws_url_with_path_prefix() -> None:
        """A custom base VWS URL with a path prefix intercepts at the
        prefix.
        """
        with MockVWS(
            base_vws_url="https://vuforia.vws.example.com/prefix",
            real_http=False,
        ):
            with pytest.raises(
                expected_exception=requests.exceptions.ConnectionError
            ):
                requests.get(
                    url="https://vuforia.vws.example.com/summary",
                    timeout=30,
                )

            requests.get(
                url="https://vuforia.vws.example.com/prefix/summary",
                timeout=30,
            )

    @staticmethod
    def test_custom_base_vwq_url_with_path_prefix() -> None:
        """A custom base VWQ URL with a path prefix intercepts at the
        prefix.
        """
        with MockVWS(
            base_vwq_url="https://vuforia.vwq.example.com/prefix",
            real_http=False,
        ):
            with pytest.raises(
                expected_exception=requests.exceptions.ConnectionError
            ):
                requests.post(
                    url="https://vuforia.vwq.example.com/v1/query",
                    timeout=30,
                )

            requests.post(
                url="https://vuforia.vwq.example.com/prefix/v1/query",
                timeout=30,
            )

    @staticmethod
    def test_vws_operations_work_with_path_prefix() -> None:
        """VWS API operations work correctly with a base URL path
        prefix.
        """
        database = CloudDatabase()
        base_vws_url = "https://vuforia.vws.example.com/prefix"

        with MockVWS(base_vws_url=base_vws_url) as mock:
            mock.add_cloud_database(cloud_database=database)

            request_path = "/targets"
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
                url=base_vws_url + request_path,
                headers={
                    "Authorization": auth,
                    "Date": date,
                },
                timeout=30,
            )

        assert response.status_code == HTTPStatus.OK
        response_json = response.json()
        assert response_json["result_code"] == "Success"
        assert response_json["results"] == []

    @staticmethod
    def test_no_scheme() -> None:
        """An error if raised if a URL is given with no scheme."""
        with pytest.raises(expected_exception=MissingSchemeError) as vws_exc:
            MockVWS(base_vws_url="vuforia.vws.example.com")

        expected = (
            'Invalid URL "vuforia.vws.example.com": No scheme supplied. '
            'Perhaps you meant "https://vuforia.vws.example.com".'
        )
        assert str(object=vws_exc.value) == expected
        with pytest.raises(expected_exception=MissingSchemeError) as vwq_exc:
            MockVWS(base_vwq_url="vuforia.vwq.example.com")
        expected = (
            'Invalid URL "vuforia.vwq.example.com": No scheme supplied. '
            'Perhaps you meant "https://vuforia.vwq.example.com".'
        )
        assert str(object=vwq_exc.value) == expected


class TestTargets:
    """Tests for target representations."""

    @staticmethod
    def test_to_dict(high_quality_image: io.BytesIO) -> None:
        """
        It is possible to dump a target to a dictionary and load it
        back.
        """
        database = CloudDatabase()

        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        with MockVWS() as mock:
            mock.add_cloud_database(cloud_database=database)
            vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )

        assert len(database.targets) == 1
        target = next(iter(database.targets))
        assert isinstance(target, ImageTarget)
        target_dict = target.to_dict()

        # The dictionary is JSON dump-able
        assert json.dumps(obj=target_dict)

        new_target = ImageTarget.from_dict(target_dict=target_dict)
        assert new_target == target

    @staticmethod
    def test_to_dict_deleted(high_quality_image: io.BytesIO) -> None:
        """
        It is possible to dump a deleted target to a dictionary and load
        it
        back.
        """
        database = CloudDatabase()

        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        with MockVWS() as mock:
            mock.add_cloud_database(cloud_database=database)
            target_id = vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            vws_client.delete_target(target_id=target_id)

        assert len(database.targets) == 1
        target = next(iter(database.targets))
        assert isinstance(target, ImageTarget)
        target_dict = target.to_dict()

        # The dictionary is JSON dump-able
        assert json.dumps(obj=target_dict)

        new_target = ImageTarget.from_dict(target_dict=target_dict)
        assert new_target.delete_date == target.delete_date

    @staticmethod
    def test_round_trip_non_default_fields(
        high_quality_image: io.BytesIO,
    ) -> None:
        """Every field of a target survives a dictionary round trip.

        The target tracking rater is deliberately not preserved:
        ``to_dict`` writes the computed tracking rating and ``from_dict``
        rebuilds the target with a hardcoded rater which gives that
        rating.
        """
        gmt = ZoneInfo(key="GMT")
        target = ImageTarget(
            active_flag=False,
            application_metadata="example-metadata",
            current_month_recos=1,
            delete_date=datetime.datetime(
                year=2020, month=1, day=4, tzinfo=gmt
            ),
            image_value=high_quality_image.getvalue(),
            last_modified_date=datetime.datetime(
                year=2020, month=1, day=3, tzinfo=gmt
            ),
            name="example",
            previous_month_recos=2,
            processing_time_seconds=0.5,
            reco_rating="example-reco-rating",
            target_id="example-target-id",
            target_tracking_rater=HardcodedTargetTrackingRater(rating=4),
            total_recos=3,
            upload_date=datetime.datetime(
                year=2020, month=1, day=2, tzinfo=gmt
            ),
            width=1.5,
        )
        # Adding a field to ``ImageTarget`` must mean adding it to this
        # test, and therefore to the round trip.
        expected_field_names = {
            "active_flag",
            "application_metadata",
            "current_month_recos",
            "delete_date",
            "image_value",
            "last_modified_date",
            "name",
            "previous_month_recos",
            "processing_time_seconds",
            "reco_rating",
            "target_id",
            "target_tracking_rater",
            "total_recos",
            "upload_date",
            "width",
        }
        field_names = {
            field.name
            for field in dataclasses.fields(class_or_instance=ImageTarget)
        }
        assert field_names == expected_field_names

        target_dict = target.to_dict()
        # The dictionary is JSON dump-able
        assert json.dumps(obj=target_dict)

        new_target = ImageTarget.from_dict(target_dict=target_dict)
        assert new_target == target
        assert new_target.tracking_rating == target.tracking_rating

    @staticmethod
    def test_vumark_target_to_dict() -> None:
        """It is possible to dump a VuMark target to a dictionary and
        load it back.
        """
        vumark_target = VuMarkTarget(
            name="example-vumark",
            processing_time_seconds=5.0,
        )
        target_dict = vumark_target.to_dict()

        assert json.dumps(obj=target_dict)

        new_target = VuMarkTarget.from_dict(target_dict=target_dict)
        assert new_target == vumark_target


class TestSetTargetRecognitionCounts:
    """Tests for setting the recognition counts of a target."""

    CURRENT_MONTH_RECOS = 3
    PREVIOUS_MONTH_RECOS = 5
    TOTAL_RECOS = 8

    def test_set_one_count(self, high_quality_image: io.BytesIO) -> None:
        """Counts which are not given are left as they are."""
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        with MockVWS() as mock:
            mock.add_cloud_database(cloud_database=database)
            target_id = vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )
            mock.set_target_recognition_counts(
                target_id=target_id,
                total_recos=self.TOTAL_RECOS,
            )
            mock.set_target_recognition_counts(
                target_id=target_id,
                current_month_recos=self.CURRENT_MONTH_RECOS,
            )

            report = vws_client.get_target_summary_report(target_id=target_id)

        assert report.total_recos == self.TOTAL_RECOS
        assert report.current_month_recos == self.CURRENT_MONTH_RECOS
        assert report.previous_month_recos == 0

    def test_recognition_counts_do_not_change_the_target(
        self,
        high_quality_image: io.BytesIO,
    ) -> None:
        """Setting recognition counts does not change the target itself.

        A target which is being recognized is not being modified, so its
        last modified date does not change, and it does not go back to
        being processed.
        """
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        with MockVWS() as mock:
            mock.add_cloud_database(cloud_database=database)
            target_id = vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            (target,) = database.targets
            last_modified_date = target.last_modified_date

            mock.set_target_recognition_counts(
                target_id=target_id,
                current_month_recos=self.CURRENT_MONTH_RECOS,
                previous_month_recos=self.PREVIOUS_MONTH_RECOS,
                total_recos=self.TOTAL_RECOS,
            )

            report = vws_client.get_target_summary_report(target_id=target_id)

        (new_target,) = database.targets
        assert new_target.last_modified_date == last_modified_date
        assert report.status == TargetStatuses.SUCCESS

    @staticmethod
    def test_unknown_target() -> None:
        """Setting the counts of an unknown target is an error."""
        database = CloudDatabase()
        target_id = uuid.uuid4().hex

        with MockVWS() as mock:
            mock.add_cloud_database(cloud_database=database)
            with pytest.raises(
                expected_exception=ValueError,
                match=f'No target has the ID "{target_id}".',
            ):
                mock.set_target_recognition_counts(
                    target_id=target_id,
                    total_recos=1,
                )


class TestDatabaseToDict:
    """Tests for dumping a database to a dictionary."""

    @staticmethod
    def test_to_dict(high_quality_image: io.BytesIO) -> None:
        """
        It is possible to dump a database to a dictionary and load it
        back.
        """
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        # We test a database with a target added.
        with MockVWS() as mock:
            mock.add_cloud_database(cloud_database=database)
            vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )

        database_dict = database.to_dict()
        # The dictionary is JSON dump-able
        assert json.dumps(obj=database_dict)

        new_database = CloudDatabase.from_dict(database_dict=database_dict)
        assert new_database == database

    @staticmethod
    def test_custom_request_quota() -> None:
        """The request quota survives a dictionary round trip."""
        database = CloudDatabase(request_quota=0)

        database_dict = database.to_dict()
        new_database = CloudDatabase.from_dict(database_dict=database_dict)

        assert new_database.request_quota == 0

    @staticmethod
    def test_custom_target_quota() -> None:
        """The target quota survives a dictionary round trip."""
        database = CloudDatabase(target_quota=0)

        database_dict = database.to_dict()
        new_database = CloudDatabase.from_dict(database_dict=database_dict)

        assert new_database.target_quota == 0

    @staticmethod
    def test_custom_requests_per_second_limit() -> None:
        """The per-second request limit survives a dictionary round
        trip.
        """
        requests_per_second_limit = 12
        database = CloudDatabase(
            requests_per_second_limit=requests_per_second_limit
        )

        database_dict = database.to_dict()
        new_database = CloudDatabase.from_dict(database_dict=database_dict)

        assert (
            new_database.requests_per_second_limit == requests_per_second_limit
        )

    @staticmethod
    def test_custom_request_rate_limits() -> None:
        """Per-endpoint request rate limits survive a dictionary round
        trip.
        """
        database = CloudDatabase(
            request_rate_limits=DOCUMENTED_REQUEST_RATE_LIMITS,
        )

        database_dict = database.to_dict()
        assert json.dumps(obj=database_dict)
        new_database = CloudDatabase.from_dict(database_dict=database_dict)

        assert (
            new_database.request_rate_limits == DOCUMENTED_REQUEST_RATE_LIMITS
        )

    @staticmethod
    def test_round_trip_non_default_fields(
        high_quality_image: io.BytesIO,
    ) -> None:
        """Every field of a database survives a dictionary round trip."""
        gmt = ZoneInfo(key="GMT")
        target = ImageTarget(
            active_flag=True,
            application_metadata=None,
            image_value=high_quality_image.getvalue(),
            last_modified_date=datetime.datetime(
                year=2020, month=1, day=3, tzinfo=gmt
            ),
            name="example",
            processing_time_seconds=0.5,
            target_tracking_rater=HardcodedTargetTrackingRater(rating=4),
            upload_date=datetime.datetime(
                year=2020, month=1, day=2, tzinfo=gmt
            ),
            width=1.5,
        )
        database = CloudDatabase(
            client_access_key="example-client-access-key",
            client_secret_key="example-client-secret-key",
            current_month_recos=1,
            database_id="example-database-id",
            database_name="example-database-name",
            # ``CLOUD_RECO`` is the only database type, so it is not
            # possible to use a non-default value here.
            database_type=DatabaseType.CLOUD_RECO,
            previous_month_recos=2,
            reco_threshold=3,
            request_quota=4,
            request_rate_limits=DOCUMENTED_REQUEST_RATE_LIMITS,
            requests_per_second_limit=5,
            server_access_key="example-server-access-key",
            server_secret_key="example-server-secret-key",
            state=States.PROJECT_SUSPENDED,
            target_quota=6,
            targets={target},
            total_recos=7,
        )
        # Adding a field to ``CloudDatabase`` must mean adding it to this
        # test, and therefore to the round trip.
        expected_field_names = {
            "client_access_key",
            "client_secret_key",
            "current_month_recos",
            "database_id",
            "database_name",
            "database_type",
            "previous_month_recos",
            "reco_threshold",
            "request_quota",
            "request_rate_limits",
            "requests_per_second_limit",
            "server_access_key",
            "server_secret_key",
            "state",
            "target_quota",
            "targets",
            "total_recos",
        }
        field_names = {
            field.name
            for field in dataclasses.fields(class_or_instance=CloudDatabase)
        }
        assert field_names == expected_field_names

        database_dict = database.to_dict()
        # The dictionary is JSON dump-able
        assert json.dumps(obj=database_dict)

        new_database = CloudDatabase.from_dict(database_dict=database_dict)
        assert new_database == database

    @staticmethod
    def test_vumark_database_to_dict() -> None:
        """It is possible to dump a VuMark database to a dictionary and
        load it back.
        """
        vumark_target = VuMarkTarget(
            name="example-vumark",
            processing_time_seconds=3.0,
        )
        database = VuMarkDatabase(
            vumark_targets={vumark_target},
        )

        database_dict = database.to_dict()
        assert json.dumps(obj=database_dict)

        new_database = VuMarkDatabase.from_dict(database_dict=database_dict)
        assert new_database == database


class TestDateHeader:
    """Tests for the date header in responses from mock routes."""

    @staticmethod
    def test_date_changes() -> None:
        """
        The date that the response is sent is in the response Date
        header.
        """
        new_year = 2012
        new_time = datetime.datetime(
            year=new_year,
            month=1,
            day=1,
            tzinfo=datetime.UTC,
        )
        with MockVWS(), freeze_time(time_to_freeze=new_time):
            response = requests.get(
                url="https://vws.vuforia.com/summary",
                timeout=30,
            )

        date_response = response.headers["Date"]
        date_from_response = email.utils.parsedate(data=date_response)
        assert date_from_response is not None
        year = date_from_response[0]
        assert year == new_year


class TestAddDatabase:
    """Tests for adding databases to the mock."""

    @staticmethod
    def test_duplicate_keys() -> None:
        """
        It is not possible to have multiple databases with matching
        keys.
        """
        database = CloudDatabase(
            server_access_key="1",
            server_secret_key="2",
            client_access_key="3",
            client_secret_key="4",
            database_name="5",
        )

        bad_server_access_key_db = CloudDatabase(server_access_key="1")
        bad_server_secret_key_db = CloudDatabase(server_secret_key="2")
        bad_client_access_key_db = CloudDatabase(client_access_key="3")
        bad_client_secret_key_db = CloudDatabase(client_secret_key="4")
        bad_database_name_db = CloudDatabase(database_name="5")

        server_access_key_conflict_error = (
            "All server access keys must be unique. "
            'There is already a database with the server access key "1".'
        )
        server_secret_key_conflict_error = (
            "All server secret keys must be unique. "
            'There is already a database with the server secret key "2".'
        )
        client_access_key_conflict_error = (
            "All client access keys must be unique. "
            'There is already a database with the client access key "3".'
        )
        client_secret_key_conflict_error = (
            "All client secret keys must be unique. "
            'There is already a database with the client secret key "4".'
        )
        database_name_conflict_error = (
            "All names must be unique. "
            'There is already a database with the name "5".'
        )

        with MockVWS() as mock:
            mock.add_cloud_database(cloud_database=database)
            for bad_database, expected_message in (
                (bad_server_access_key_db, server_access_key_conflict_error),
                (bad_server_secret_key_db, server_secret_key_conflict_error),
                (bad_client_access_key_db, client_access_key_conflict_error),
                (bad_client_secret_key_db, client_secret_key_conflict_error),
                (bad_database_name_db, database_name_conflict_error),
            ):
                with pytest.raises(
                    expected_exception=ValueError,
                    match=expected_message + "$",
                ):
                    mock.add_cloud_database(cloud_database=bad_database)

    @staticmethod
    def test_duplicate_vumark_keys() -> None:
        """
        It is not possible to have multiple databases with matching
        keys, including VuMark databases.
        """
        database = VuMarkDatabase(
            server_access_key="1",
            server_secret_key="2",
            database_name="3",
        )

        bad_server_access_key_db = VuMarkDatabase(server_access_key="1")
        bad_server_secret_key_db = VuMarkDatabase(server_secret_key="2")
        bad_database_name_db = VuMarkDatabase(database_name="3")

        server_access_key_conflict_error = (
            "All server access keys must be unique. "
            'There is already a database with the server access key "1".'
        )
        server_secret_key_conflict_error = (
            "All server secret keys must be unique. "
            'There is already a database with the server secret key "2".'
        )
        database_name_conflict_error = (
            "All names must be unique. "
            'There is already a database with the name "3".'
        )

        with MockVWS() as mock:
            mock.add_vumark_database(vumark_database=database)
            for bad_database, expected_message in (
                (bad_server_access_key_db, server_access_key_conflict_error),
                (bad_server_secret_key_db, server_secret_key_conflict_error),
                (bad_database_name_db, database_name_conflict_error),
            ):
                with pytest.raises(
                    expected_exception=ValueError,
                    match=expected_message + "$",
                ):
                    mock.add_vumark_database(vumark_database=bad_database)

    @staticmethod
    def test_vumark_database_added_before_entering() -> None:
        """A VuMark database added before the mock starts is available
        while the mock is running.
        """
        database = VuMarkDatabase(database_name="vumark-before-enter")
        mock = MockVWS()
        mock.add_vumark_database(vumark_database=database)
        conflicting_database = VuMarkDatabase(
            database_name="vumark-before-enter",
        )
        expected_message = (
            "All names must be unique. "
            "There is already a database with the name "
            '"vumark-before-enter".'
        )
        with (
            mock,
            pytest.raises(
                expected_exception=ValueError,
                match=expected_message + "$",
            ),
        ):
            mock.add_vumark_database(
                vumark_database=conflicting_database,
            )


class TestContextManagerReuse:
    """Tests for reusing a ``MockVWS`` instance as a context manager."""

    @staticmethod
    def test_state_is_kept_between_uses(
        high_quality_image: io.BytesIO,
    ) -> None:
        """A ``MockVWS`` instance keeps its databases, and the targets in
        them, between ``with`` blocks.
        """
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        mock = MockVWS()
        mock.add_cloud_database(cloud_database=database)

        with mock:
            vws_client.add_target(
                name="my-target",
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )
            assert len(vws_client.list_targets()) == 1

        with mock:
            assert len(vws_client.list_targets()) == 1


class TestQueryImageMatchers:
    """Tests for query image matchers."""

    @staticmethod
    def test_exact_match(high_quality_image: io.BytesIO) -> None:
        """The exact matcher matches only exactly the same images."""
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        cloud_reco_client = CloudRecoService(
            client_access_key=database.client_access_key,
            client_secret_key=database.client_secret_key,
        )

        pil_image = Image.open(fp=high_quality_image)
        re_exported_image = io.BytesIO()
        pil_image.save(fp=re_exported_image, format="PNG")

        with MockVWS(query_match_checker=ExactMatcher()) as mock:
            mock.add_cloud_database(cloud_database=database)
            target_id = vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            same_image_result = cloud_reco_client.query(
                image=high_quality_image,
            )
            assert len(same_image_result) == 1
            different_image_result = cloud_reco_client.query(
                image=re_exported_image,
            )
            assert not different_image_result

    @staticmethod
    def test_custom_matcher(high_quality_image: io.BytesIO) -> None:
        """It is possible to use a custom matcher."""
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        cloud_reco_client = CloudRecoService(
            client_access_key=database.client_access_key,
            client_secret_key=database.client_secret_key,
        )

        pil_image = Image.open(fp=high_quality_image)
        re_exported_image = io.BytesIO()
        pil_image.save(fp=re_exported_image, format="PNG")

        with MockVWS(query_match_checker=_not_exact_matcher) as mock:
            mock.add_cloud_database(cloud_database=database)
            target_id = vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            same_image_result = cloud_reco_client.query(
                image=high_quality_image,
            )
            assert not same_image_result
            different_image_result = cloud_reco_client.query(
                image=re_exported_image,
            )
            assert len(different_image_result) == 1

    @staticmethod
    def test_structural_similarity_matcher(
        *,
        high_quality_image: io.BytesIO,
        different_high_quality_image: io.BytesIO,
    ) -> None:
        """The structural similarity matcher matches similar images."""
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        cloud_reco_client = CloudRecoService(
            client_access_key=database.client_access_key,
            client_secret_key=database.client_secret_key,
        )

        pil_image = Image.open(fp=high_quality_image)
        re_exported_image = io.BytesIO()
        pil_image.save(fp=re_exported_image, format="PNG")

        with MockVWS(
            query_match_checker=StructuralSimilarityMatcher(),
        ) as mock:
            mock.add_cloud_database(cloud_database=database)
            target_id = vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            same_image_result = cloud_reco_client.query(
                image=high_quality_image,
            )
            assert len(same_image_result) == 1
            similar_image_result = cloud_reco_client.query(
                image=re_exported_image,
            )
            assert len(similar_image_result) == 1

            different_image_result = cloud_reco_client.query(
                image=different_high_quality_image,
            )
            assert not different_image_result

    @staticmethod
    def test_results_are_ordered_by_match_score(
        *,
        high_quality_image: io.BytesIO,
        different_high_quality_image: io.BytesIO,
    ) -> None:
        """Query results are ordered by match score, best match first."""
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        cloud_reco_client = CloudRecoService(
            client_access_key=database.client_access_key,
            client_secret_key=database.client_secret_key,
        )

        with MockVWS(query_match_checker=_image_length_matcher) as mock:
            mock.add_cloud_database(cloud_database=database)
            first_target_id = vws_client.add_target(
                name="example_0",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            second_target_id = vws_client.add_target(
                name="example_1",
                width=1,
                image=different_high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            vws_client.wait_for_target_processed(target_id=first_target_id)
            vws_client.wait_for_target_processed(target_id=second_target_id)

            # The second target's image is an exact length match for the
            # query image, so it comes first despite being uploaded last.
            results = cloud_reco_client.query(
                image=different_high_quality_image,
                max_num_results=2,
            )
            result_target_ids = [result.target_id for result in results]
            assert result_target_ids == [second_target_id, first_target_id]

            results = cloud_reco_client.query(
                image=high_quality_image,
                max_num_results=2,
            )
            result_target_ids = [result.target_id for result in results]
            assert result_target_ids == [first_target_id, second_target_id]

    @staticmethod
    def test_bool_matcher(high_quality_image: io.BytesIO) -> None:
        """A matcher which returns a ``bool`` gives a useful error.

        Matchers used to answer yes or no; they now give a score.
        """
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        cloud_reco_client = CloudRecoService(
            client_access_key=database.client_access_key,
            client_secret_key=database.client_secret_key,
        )

        with MockVWS(query_match_checker=_bool_matcher) as mock:
            mock.add_cloud_database(cloud_database=database)
            target_id = vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            expected_message = (
                "Image matchers must return a score or None, but .* "
                "returned True."
            )
            with pytest.raises(
                expected_exception=TypeError,
                match=expected_message,
            ):
                cloud_reco_client.query(image=high_quality_image)


class TestDuplicatesImageMatchers:
    """Tests for duplicates image matchers."""

    @staticmethod
    def test_exact_match(high_quality_image: io.BytesIO) -> None:
        """The exact matcher matches only exactly the same images."""
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        pil_image = Image.open(fp=high_quality_image)
        re_exported_image = io.BytesIO()
        pil_image.save(fp=re_exported_image, format="PNG")

        with MockVWS(duplicate_match_checker=ExactMatcher()) as mock:
            mock.add_cloud_database(cloud_database=database)
            target_id = vws_client.add_target(
                name="example_0",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            duplicate_target_id = vws_client.add_target(
                name="example_1",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            not_duplicate_target_id = vws_client.add_target(
                name="example_2",
                width=1,
                image=re_exported_image,
                application_metadata=None,
                active_flag=True,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            vws_client.wait_for_target_processed(target_id=duplicate_target_id)
            vws_client.wait_for_target_processed(
                target_id=not_duplicate_target_id,
            )
            duplicates = vws_client.get_duplicate_targets(target_id=target_id)
            assert duplicates == [duplicate_target_id]

    @staticmethod
    def test_custom_matcher(high_quality_image: io.BytesIO) -> None:
        """It is possible to use a custom matcher."""
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        pil_image = Image.open(fp=high_quality_image)
        re_exported_image = io.BytesIO()
        pil_image.save(fp=re_exported_image, format="PNG")

        with MockVWS(duplicate_match_checker=_not_exact_matcher) as mock:
            mock.add_cloud_database(cloud_database=database)
            target_id = vws_client.add_target(
                name="example_0",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            duplicate_target_id = vws_client.add_target(
                name="example_1",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            not_duplicate_target_id = vws_client.add_target(
                name="example_2",
                width=1,
                image=re_exported_image,
                application_metadata=None,
                active_flag=True,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            vws_client.wait_for_target_processed(target_id=duplicate_target_id)
            vws_client.wait_for_target_processed(
                target_id=not_duplicate_target_id,
            )
            duplicates = vws_client.get_duplicate_targets(target_id=target_id)
            assert duplicates == [not_duplicate_target_id]

    @staticmethod
    def test_structural_similarity_matcher(
        high_quality_image: io.BytesIO,
    ) -> None:
        """The structural similarity matcher matches similar images."""
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        pil_image = Image.open(fp=high_quality_image)
        re_exported_image = io.BytesIO()
        pil_image.save(fp=re_exported_image, format="PNG")

        with MockVWS(
            duplicate_match_checker=StructuralSimilarityMatcher(),
        ) as mock:
            mock.add_cloud_database(cloud_database=database)
            target_id = vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            duplicate_target_id = vws_client.add_target(
                name="example_1",
                width=1,
                image=re_exported_image,
                application_metadata=None,
                active_flag=True,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            vws_client.wait_for_target_processed(target_id=duplicate_target_id)
            duplicates = vws_client.get_duplicate_targets(target_id=target_id)
            assert duplicates == [duplicate_target_id]

    @staticmethod
    def test_results_are_ordered_by_match_score(
        *,
        high_quality_image: io.BytesIO,
        different_high_quality_image: io.BytesIO,
    ) -> None:
        """Duplicates are ordered by match score, best match first."""
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        with MockVWS(duplicate_match_checker=_image_length_matcher) as mock:
            mock.add_cloud_database(cloud_database=database)
            target_id = vws_client.add_target(
                name="example_0",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            different_image_target_id = vws_client.add_target(
                name="example_1",
                width=1,
                image=different_high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            same_image_target_id = vws_client.add_target(
                name="example_2",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            for created_target_id in (
                target_id,
                different_image_target_id,
                same_image_target_id,
            ):
                vws_client.wait_for_target_processed(
                    target_id=created_target_id,
                )

            # The last uploaded target's image is an exact length match, so
            # it comes first.
            duplicates = vws_client.get_duplicate_targets(target_id=target_id)
            assert duplicates == [
                same_image_target_id,
                different_image_target_id,
            ]


# This is in the wrong file really as it hits both the in memory mock and the
# Flask app.
@pytest.mark.usefixtures("mock_only_vuforia")
class TestDataTypes:
    """Tests for sending various data types."""

    @staticmethod
    def test_text(endpoint: Endpoint) -> None:
        """It is possible to send strings to VWS endpoints."""
        netloc = urlparse(url=endpoint.base_url).netloc

        if netloc == "cloudreco.vuforia.com":
            pytest.skip()

        assert isinstance(endpoint.data, bytes)
        new_endpoint = Endpoint(
            base_url=endpoint.base_url,
            path_url=endpoint.path_url,
            method=endpoint.method,
            headers=endpoint.headers,
            data=endpoint.data.decode(encoding="utf-8"),
            successful_headers_result_code=endpoint.successful_headers_result_code,
            successful_headers_status_code=endpoint.successful_headers_status_code,
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
        )
        response = new_endpoint.send()
        assert response.status_code == endpoint.successful_headers_status_code


class TestHttpxAlsoIntercepted:
    """Tests that MockVWS also intercepts httpx requests."""

    @staticmethod
    def test_httpx_vuforia_endpoint_intercepted() -> None:
        """``MockVWS`` intercepts ``httpx`` requests to Vuforia
        endpoints.
        """
        with MockVWS():
            response = httpx.get(
                url="https://vws.vuforia.com/summary",
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                timeout=30,
            )
        assert response.status_code is not None

    @staticmethod
    def test_httpx_unmocked_address_blocked() -> None:
        """``MockVWS`` blocks ``httpx`` requests to non-Vuforia
        addresses.
        """
        sock = socket.socket()
        sock.bind(("", 0))
        port = sock.getsockname()[1]
        sock.close()
        with MockVWS(), pytest.raises(expected_exception=httpx.ConnectError):
            httpx.get(url=f"http://localhost:{port}", timeout=30)

    @staticmethod
    def test_httpx_real_http() -> None:
        """When ``real_http=True``, ``httpx`` requests to non-Vuforia
        addresses are not blocked.
        """
        sock = socket.socket()
        sock.bind(("", 0))
        port = sock.getsockname()[1]
        sock.close()
        with (
            MockVWS(real_http=True),
            pytest.raises(expected_exception=httpx.ConnectError),
        ):
            httpx.get(url=f"http://localhost:{port}", timeout=30)


class TestHttpx2AlsoIntercepted:
    """Tests that MockVWS also intercepts httpx2 requests."""

    @staticmethod
    def test_httpx2_vuforia_endpoint_intercepted() -> None:
        """``MockVWS`` intercepts ``httpx2`` requests to Vuforia
        endpoints.
        """
        with MockVWS():
            response = httpx2.get(
                url="https://vws.vuforia.com/summary",
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                timeout=30,
            )
        assert response.status_code is not None

    @staticmethod
    def test_httpx2_client_made_before_start_intercepted() -> None:
        """A client which was made before the mock started is
        intercepted.
        """
        with httpx2.Client() as client, MockVWS():
            response = client.get(
                url="https://vws.vuforia.com/summary",
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                timeout=30,
            )
        assert response.status_code == HTTPStatus.BAD_REQUEST

    @staticmethod
    def test_httpx2_unmocked_address_blocked() -> None:
        """``MockVWS`` blocks ``httpx2`` requests to non-Vuforia
        addresses.
        """
        sock = socket.socket()
        sock.bind(("", 0))
        port = sock.getsockname()[1]
        sock.close()
        with MockVWS(), pytest.raises(expected_exception=httpx2.ConnectError):
            httpx2.get(url=f"http://localhost:{port}", timeout=30)

    @staticmethod
    def test_httpx2_real_http() -> None:
        """When ``real_http=True``, ``httpx2`` requests to non-Vuforia
        addresses are not blocked.
        """
        sock = socket.socket()
        sock.bind(("", 0))
        port = sock.getsockname()[1]
        sock.close()
        with (
            MockVWS(real_http=True),
            pytest.raises(expected_exception=httpx2.ConnectError),
        ):
            httpx2.get(url=f"http://localhost:{port}", timeout=30)


class TestModelTargetWebAPI:
    """Tests for the Model Target Web API."""

    @staticmethod
    def test_standard_dataset_workflow() -> None:
        """A standard Model Target dataset can be created and
        downloaded.
        """
        with MockVWS(processing_time_seconds=0):
            token_response = requests.post(
                url="https://vws.vuforia.com/oauth2/token",
                auth=("client-id", "client-secret"),
                data={"grant_type": "client_credentials"},
                timeout=30,
            )
            token = token_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            create_response = requests.post(
                url="https://vws.vuforia.com/modeltargets/datasets",
                headers=headers,
                json=_MODEL_TARGET_DATASET_REQUEST,
                timeout=30,
            )
            dataset_uuid = create_response.json()["uuid"]

            status_response = requests.get(
                url=(
                    "https://vws.vuforia.com/modeltargets/datasets/"
                    f"{dataset_uuid}/status"
                ),
                headers=headers,
                timeout=30,
            )
            dataset_response = requests.get(
                url=(
                    "https://vws.vuforia.com/modeltargets/datasets/"
                    f"{dataset_uuid}/dataset"
                ),
                headers=headers,
                timeout=30,
            )

        assert token_response.status_code == HTTPStatus.OK
        assert create_response.status_code == HTTPStatus.CREATED
        assert status_response.json()["status"] == "done"
        with zipfile.ZipFile(
            file=io.BytesIO(initial_bytes=dataset_response.content),
        ) as dataset_zip:
            assert dataset_zip.namelist() == ["MTDataset.dat", "MTDataset.xml"]

    @staticmethod
    def test_advanced_dataset_workflow() -> None:
        """An advanced Model Target dataset can be created."""
        with MockVWS(processing_time_seconds=0):
            response = requests.post(
                url="https://vws.vuforia.com/modeltargets/advancedDatasets",
                headers={"Authorization": _MODEL_TARGET_AUTHORIZATION},
                json=_MODEL_TARGET_DATASET_REQUEST,
                timeout=30,
            )
            dataset_uuid = response.json()["uuid"]
            status_response = requests.get(
                url=(
                    "https://vws.vuforia.com/modeltargets/"
                    f"advancedDatasets/{dataset_uuid}/status"
                ),
                headers={"Authorization": _MODEL_TARGET_AUTHORIZATION},
                timeout=30,
            )

        assert response.status_code == HTTPStatus.CREATED
        assert status_response.json()["uuid"] == dataset_uuid

    @staticmethod
    def test_dataset_download_is_reproducible() -> None:
        """Downloading the same dataset produces identical bytes."""
        headers = {"Authorization": _MODEL_TARGET_AUTHORIZATION}
        with MockVWS(processing_time_seconds=0):
            with freeze_time(time_to_freeze="2026-01-01"):
                create_response = requests.post(
                    url="https://vws.vuforia.com/modeltargets/datasets",
                    headers=headers,
                    json=_MODEL_TARGET_DATASET_REQUEST,
                    timeout=30,
                )
            dataset_uuid = create_response.json()["uuid"]
            dataset_url = (
                "https://vws.vuforia.com/modeltargets/datasets/"
                f"{dataset_uuid}/dataset"
            )
            with freeze_time(time_to_freeze="2026-01-02"):
                first_response = requests.get(
                    url=dataset_url,
                    headers=headers,
                    timeout=30,
                )
            with freeze_time(time_to_freeze="2027-01-02"):
                second_response = requests.get(
                    url=dataset_url,
                    headers=headers,
                    timeout=30,
                )

        assert first_response.status_code == HTTPStatus.OK
        assert second_response.status_code == HTTPStatus.OK
        assert first_response.content == second_response.content

    @staticmethod
    def test_bearer_token_required() -> None:
        """Model Target dataset routes require a bearer token."""
        with MockVWS():
            response = requests.post(
                url="https://vws.vuforia.com/modeltargets/datasets",
                json=_MODEL_TARGET_DATASET_REQUEST,
                timeout=30,
            )

        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert response.json()["error"] == {
            "code": "401",
            "message": "no Bearer token",
            "target": "jwt",
        }


class TestDecorator:
    """Tests for using the mock as a decorator."""

    @staticmethod
    def test_requests_are_mocked_only_within_the_function() -> None:
        """Requests to Vuforia are mocked within the decorated function,
        and
        they are not mocked once the decorated function has returned.
        """
        base_vws_url = _unused_local_url()
        summary_url = base_vws_url + "/summary"

        @MockVWS(base_vws_url=base_vws_url)
        def make_request() -> requests.Response:
            """Make a request to the mocked VWS API."""
            return requests.get(
                url=summary_url,
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                data=b"",
                timeout=30,
            )

        response = make_request()
        assert response.status_code == HTTPStatus.BAD_REQUEST

        # Nothing is listening on the given address, so this shows that the
        # mocking stops when the decorated function returns.
        with pytest.raises(
            expected_exception=requests.exceptions.ConnectionError
        ):
            requests.get(url=summary_url, timeout=30)

    @staticmethod
    def test_httpx_requests_are_mocked() -> None:
        """Requests made with ``httpx`` are mocked within the decorated
        function.
        """
        base_vws_url = _unused_local_url()
        summary_url = base_vws_url + "/summary"

        @MockVWS(base_vws_url=base_vws_url)
        def make_request() -> httpx.Response:
            """Make a request to the mocked VWS API."""
            return httpx.get(
                url=summary_url,
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                timeout=30,
            )

        response = make_request()
        assert response.status_code == HTTPStatus.BAD_REQUEST

        with pytest.raises(expected_exception=httpx.ConnectError):
            httpx.get(url=summary_url, timeout=30)

    @staticmethod
    def test_httpx2_requests_are_mocked() -> None:
        """Requests made with ``httpx2`` are mocked within the decorated
        function.
        """
        base_vws_url = _unused_local_url()
        summary_url = base_vws_url + "/summary"

        @MockVWS(base_vws_url=base_vws_url)
        def make_request() -> httpx2.Response:
            """Make a request to the mocked VWS API."""
            return httpx2.get(
                url=summary_url,
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                timeout=30,
            )

        response = make_request()
        assert response.status_code == HTTPStatus.BAD_REQUEST

        with pytest.raises(expected_exception=httpx2.ConnectError):
            httpx2.get(url=summary_url, timeout=30)

    @staticmethod
    def test_arguments_and_return_value() -> None:
        """Arguments are passed to the decorated function, and its return
        value is returned.
        """

        @MockVWS()
        def join(*parts: str, separator: str) -> str:
            """Join the given parts."""
            return separator.join(parts)

        assert join("a", "b", separator="-") == "a-b"

    @staticmethod
    def test_function_metadata_is_preserved() -> None:
        """The decorated function keeps its name and docstring."""

        @MockVWS()
        def my_function() -> None:
            """My docstring."""

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    @staticmethod
    def test_databases_added_before_decorating() -> None:
        """Databases added to the mock are available within the decorated
        function.
        """
        database = CloudDatabase()
        mock = MockVWS()
        mock.add_cloud_database(cloud_database=database)

        @mock
        def get_database_name() -> str:
            """Get the name of the database from the mock."""
            vws_client = VWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
            )
            return vws_client.get_database_summary_report().name

        assert get_database_name() == database.database_name

    @staticmethod
    def test_vumark_database_added_before_decorating() -> None:
        """VuMark databases are available within a decorated function."""
        vumark_target = VuMarkTarget(name="test-target")
        database = VuMarkDatabase(vumark_targets={vumark_target})
        mock = MockVWS()
        mock.add_vumark_database(vumark_database=database)

        @mock
        def generate_vumark_instance() -> bytes:
            """Generate a VuMark instance from the configured database."""
            client = VuMarkService(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
            )
            return client.generate_vumark_instance(
                target_id=vumark_target.target_id,
                instance_id=uuid.uuid4().hex,
                accept=VuMarkAccept.PNG,
            )

        assert generate_vumark_instance().startswith(b"\x89PNG")

    @staticmethod
    def test_options_are_used(image_file_failed_state: io.BytesIO) -> None:
        """Options given to the mock are used within the decorated
        function.
        """
        database = CloudDatabase()
        mock = MockVWS(processing_time_seconds=0)
        mock.add_cloud_database(cloud_database=database)

        @mock
        def add_target() -> TargetStatuses:
            """Add a target and return its status immediately."""
            vws_client = VWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
            )
            target_id = vws_client.add_target(
                name="example",
                width=1,
                image=image_file_failed_state,
                active_flag=True,
                application_metadata=None,
            )
            return vws_client.get_target_record(target_id=target_id).status

        # The given processing time of zero seconds means that the target is
        # processed immediately.
        assert add_target() == TargetStatuses.FAILED

    @staticmethod
    def test_vumark_targets_are_restored() -> None:
        """VuMark targets changed during a call of a decorated function
        are put back as they were afterwards, just as Cloud targets
        are.
        """
        vumark_target = VuMarkTarget(name="existing-target")
        database = VuMarkDatabase(vumark_targets={vumark_target})
        mock = MockVWS()
        mock.add_vumark_database(vumark_database=database)

        temporary_target = VuMarkTarget(name="temporary")

        @mock
        def add_temporary_target() -> None:
            """Add a target to the database object directly."""
            database.vumark_targets.add(temporary_target)
            assert database.vumark_targets == {
                vumark_target,
                temporary_target,
            }

        add_temporary_target()
        assert database.vumark_targets == {vumark_target}

    @staticmethod
    def test_each_call_is_isolated(high_quality_image: io.BytesIO) -> None:
        """Each call of a decorated function has its own targets.

        Targets created by one call are not there in the next call, or in a
        call of another function decorated with the same instance.
        """
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        mock = MockVWS(processing_time_seconds=0)
        mock.add_cloud_database(cloud_database=database)

        @mock
        def add_one_target() -> None:
            """Add a target with a name used only once per call."""
            vws_client.add_target(
                name="only-one",
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )
            assert len(vws_client.list_targets()) == 1

        @mock
        def count_targets() -> int:
            """Return the number of targets in the database."""
            return len(vws_client.list_targets())

        add_one_target()
        assert count_targets() == 0
        add_one_target()
        assert count_targets() == 0

    @staticmethod
    def test_nested_calls(high_quality_image: io.BytesIO) -> None:
        """A decorated function can call another decorated function.

        The inner call starts from the targets which are there when it is
        called, and the targets it creates are gone once it has returned. The
        outer call keeps its own targets and its mocking.
        """
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        mock = MockVWS(processing_time_seconds=0)
        mock.add_cloud_database(cloud_database=database)

        @mock
        def add_inner_target() -> int:
            """Add a target and return the number of targets.

            Returns:
                The number of targets, including the one added here.
            """
            vws_client.add_target(
                name="inner",
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )
            return len(vws_client.list_targets())

        @mock
        def add_outer_target() -> tuple[int, int]:
            """Add a target and make an inner call.

            Returns:
                The number of targets seen by the inner call, and the number
                of targets seen here once the inner call has returned.
            """
            vws_client.add_target(
                name="outer",
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )
            return add_inner_target(), len(vws_client.list_targets())

        targets_seen_by_inner_call = 2
        inner_count, outer_count = add_outer_target()
        assert inner_count == targets_seen_by_inner_call
        assert outer_count == 1
        assert not database.targets

    @staticmethod
    def test_database_targets_are_restored(
        high_quality_image: io.BytesIO,
    ) -> None:
        """A database is restored to the targets it had before a call.

        The targets can be inspected during the call, and they are what they
        were before the call again once it returns.
        """
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        mock = MockVWS(processing_time_seconds=0)
        mock.add_cloud_database(cloud_database=database)

        @mock
        def add_one_target() -> None:
            """Add a target and inspect it on the database object."""
            vws_client.add_target(
                name="only-one",
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )
            (target,) = database.targets
            assert target.name == "only-one"

        add_one_target()
        assert not database.targets

    @staticmethod
    def test_exception_restores_database_targets(
        high_quality_image: io.BytesIO,
    ) -> None:
        """The targets of a database are restored even when the decorated
        function raises.
        """
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        mock = MockVWS(processing_time_seconds=0)
        mock.add_cloud_database(cloud_database=database)

        @mock
        def add_one_target_then_raise() -> None:
            """Add a target and then raise an exception.

            Raises:
                ValueError: Always.
            """
            vws_client.add_target(
                name="only-one",
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )
            message = "Something went wrong."
            raise ValueError(message)

        with pytest.raises(
            expected_exception=ValueError,
            match=r"^Something went wrong\.$",
        ):
            add_one_target_then_raise()

        assert not database.targets

    @staticmethod
    def test_query(high_quality_image: io.BytesIO) -> None:
        """Query requests are mocked within the decorated function."""
        database = CloudDatabase()
        mock = MockVWS(processing_time_seconds=0)
        mock.add_cloud_database(cloud_database=database)

        @mock
        def query() -> tuple[str, list[str]]:
            """Add a target and query for it."""
            vws_client = VWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
            )
            target_id = vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            cloud_reco_client = CloudRecoService(
                client_access_key=database.client_access_key,
                client_secret_key=database.client_secret_key,
                transport=HTTPXTransport(),
            )
            matches = cloud_reco_client.query(image=high_quality_image)
            return target_id, [match.target_id for match in matches]

        added_target_id, matching_target_ids = query()
        assert matching_target_ids == [added_target_id]

    @staticmethod
    def test_decorating_a_method() -> None:
        """It is possible to decorate a method."""
        database = CloudDatabase()
        mock = MockVWS()
        mock.add_cloud_database(cloud_database=database)

        class _Example:
            """A class with a decorated method."""

            @mock
            def get_database_name(self) -> str:
                """Get the name of the database from the mock."""
                assert self is not None
                vws_client = VWS(
                    server_access_key=database.server_access_key,
                    server_secret_key=database.server_secret_key,
                )
                return vws_client.get_database_summary_report().name

        assert _Example().get_database_name() == database.database_name
