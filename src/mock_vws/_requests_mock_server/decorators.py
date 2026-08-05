"""Decorators for using the mock."""

import re
import time
from collections.abc import Callable, Mapping
from contextlib import ContextDecorator
from typing import TYPE_CHECKING, Any, Literal, Self
from urllib.parse import urlparse

import requests
from beartype import BeartypeConf, beartype
from requests import PreparedRequest
from responses import RequestsMock

from mock_vws._mock_common import MissingSchemeError, RequestData
from mock_vws._respx_mock_server.decorators import start_respx_router
from mock_vws.cloud_query import CloudQueryFailureResponse
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.image_matchers import (
    ImageMatcher,
    StructuralSimilarityMatcher,
)
from mock_vws.model_target import (
    ModelTargetGenerationFailure,
    ModelTargetGenerationWarning,
)
from mock_vws.target_manager import TargetManager
from mock_vws.target_raters import (
    BrisqueTargetTrackingRater,
    TargetTrackingRater,
)
from mock_vws.vumark import VuMarkGenerationFailure

from .mock_web_query_api import MockVuforiaWebQueryAPI
from .mock_web_services_api import MockVuforiaWebServicesAPI

if TYPE_CHECKING:
    import respx

_ResponseType = tuple[int, Mapping[str, str], str | bytes]
_MockCallback = Callable[[RequestData], _ResponseType]
_ResponsesCallback = Callable[[PreparedRequest], _ResponseType]

_STRUCTURAL_SIMILARITY_MATCHER = StructuralSimilarityMatcher()
_BRISQUE_TRACKING_RATER = BrisqueTargetTrackingRater()


@beartype(conf=BeartypeConf(is_pep484_tower=True))
class MockVWS(ContextDecorator):
    """Route requests to Vuforia's Web Service APIs to fakes of those APIs.

    Works with both ``requests`` and ``httpx``.
    """

    def __init__(
        self,
        *,
        base_vws_url: str = "https://vws.vuforia.com",
        base_vwq_url: str = "https://cloudreco.vuforia.com",
        cloud_query_failure_response: CloudQueryFailureResponse | None = None,
        duplicate_match_checker: ImageMatcher = _STRUCTURAL_SIMILARITY_MATCHER,
        query_match_checker: ImageMatcher = _STRUCTURAL_SIMILARITY_MATCHER,
        processing_time_seconds: float = 2.0,
        model_target_generation_failure: (
            ModelTargetGenerationFailure | None
        ) = None,
        model_target_generation_warning: (
            ModelTargetGenerationWarning | None
        ) = None,
        target_tracking_rater: TargetTrackingRater = _BRISQUE_TRACKING_RATER,
        real_http: bool = False,
        response_delay_seconds: float = 0.0,
        sleep_fn: Callable[[float], None] = time.sleep,
        vumark_generation_failure: VuMarkGenerationFailure | None = None,
    ) -> None:
        """Route requests to Vuforia's Web Service APIs to fakes of those
        APIs.

        Works with both ``requests`` and ``httpx``.

        Args:
            real_http: Whether or not to forward requests to the real
                server if they are not handled by the mock.
                See
                https://requests-mock.readthedocs.io/en/latest/mocker.html#real-http-requests.
            processing_time_seconds: The number of seconds to process each
                image for.
                In the real Vuforia Web Services, this is not deterministic.
            model_target_generation_failure: A failure to return after every
                Model Target dataset finishes processing. By default, Model
                Target datasets finish successfully.
            model_target_generation_warning: A warning to return after every
                Model Target dataset finishes processing. By default, Model
                Target datasets finish without warnings. This cannot be
                combined with ``model_target_generation_failure``.
            base_vwq_url: The base URL for the VWQ API.
            base_vws_url: The base URL for the VWS API.
            cloud_query_failure_response: A response to return for every Cloud
                Query request, bypassing normal request validation and image
                matching. By default, Cloud Query requests are handled
                normally.
            vumark_generation_failure: A failure to return for every VuMark
                generation request, bypassing normal request validation and
                instance generation. By default, VuMark generation requests
                are handled normally.
            query_match_checker: A callable which takes two image values and
                returns whether they will match in a query request.
            duplicate_match_checker: A callable which takes two image values
                and returns whether they are duplicates.
            target_tracking_rater: A callable for rating targets for tracking.
            response_delay_seconds: The number of seconds to delay each
                response by. This can be used to test timeout handling.
            sleep_fn: The function to use for sleeping during response
                delays. Defaults to ``time.sleep``. Inject a custom
                function to control virtual time in tests without
                monkey-patching.

        Raises:
            MissingSchemeError: There is no scheme in a given URL.
            ValueError: Both a Model Target generation failure and warning are
                configured.
        """
        super().__init__()
        if (
            model_target_generation_failure is not None
            and model_target_generation_warning is not None
        ):
            msg = (
                "Model Target generation failure and warning configurations "
                "are mutually exclusive"
            )
            raise ValueError(msg)
        self._real_http = real_http
        self._response_delay_seconds = response_delay_seconds
        self._sleep_fn = sleep_fn
        self._mock: RequestsMock
        self._router: respx.MockRouter
        self._target_manager = TargetManager()

        self._base_vws_url = base_vws_url
        self._base_vwq_url = base_vwq_url
        for url in (base_vwq_url, base_vws_url):
            parse_result = urlparse(url=url)
            if not parse_result.scheme:
                raise MissingSchemeError(url=url)

        self._mock_vws_api = MockVuforiaWebServicesAPI(
            target_manager=self._target_manager,
            processing_time_seconds=float(processing_time_seconds),
            model_target_generation_failure=model_target_generation_failure,
            model_target_generation_warning=model_target_generation_warning,
            duplicate_match_checker=duplicate_match_checker,
            target_tracking_rater=target_tracking_rater,
            vumark_generation_failure=vumark_generation_failure,
        )

        self._mock_vwq_api = MockVuforiaWebQueryAPI(
            target_manager=self._target_manager,
            query_match_checker=query_match_checker,
            failure_response=cloud_query_failure_response,
        )

    def add_cloud_database(self, cloud_database: CloudDatabase) -> None:
        """Add a cloud database.

        Args:
            cloud_database: The cloud database to add.

        Raises:
            ValueError: One of the given cloud database keys matches a key for
                an existing cloud database.
        """
        self._target_manager.add_cloud_database(
            cloud_database=cloud_database,
        )

    def add_vumark_database(self, vumark_database: VuMarkDatabase) -> None:
        """Add a VuMark database.

        Args:
            vumark_database: The VuMark database to add.

        Raises:
            ValueError: One of the given database keys matches a key for
                an existing database.
        """
        self._target_manager.add_vumark_database(
            vumark_database=vumark_database,
        )

    @staticmethod
    def _wrap_callback(
        callback: _MockCallback,
        delay_seconds: float,
        sleep_fn: Callable[[float], None],
        base_path: str,
    ) -> _ResponsesCallback:
        """Wrap a callback to add a response delay."""

        def wrapped(
            request: PreparedRequest,
        ) -> _ResponseType:
            """Handle the response delay and timeout logic."""
            # req_kwargs is added dynamically by the responses
            # library onto PreparedRequest objects - it is not
            # in the requests type stubs.
            req_kwargs: dict[str, Any] = getattr(  # pylint: disable=bad-builtin
                request,
                "req_kwargs",
                {},
            )
            timeout: tuple[float, float] | float | int | None = req_kwargs.get(
                "timeout"
            )
            # requests allows timeout as a (connect, read)
            # tuple. The delay simulates server response
            # time, so compare against the read timeout.
            match timeout:
                case (_, int() | float() as read_timeout):
                    effective: float | None = float(read_timeout)
                case int() | float():
                    effective = float(timeout)
                case _:
                    effective = None

            if effective is not None and delay_seconds > effective:
                sleep_fn(effective)
                raise requests.exceptions.Timeout

            match request.body:
                case None:
                    body_bytes = b""
                case str() as raw_body:
                    body_bytes = raw_body.encode(encoding="utf-8")
                case _:
                    body_bytes = request.body

            path = request.path_url
            if base_path and path.startswith(base_path):
                path = path[len(base_path) :]

            request_data = RequestData(
                method=request.method or "",
                path=path,
                headers=dict(request.headers),
                body=body_bytes,
            )
            result = callback(request_data)
            sleep_fn(delay_seconds)
            return result

        return wrapped

    def __enter__(self) -> Self:
        """Start an instance of a Vuforia mock.

        Returns:
            ``self``.
        """
        mock = RequestsMock(assert_all_requests_are_fired=False)

        for api, base_url in (
            (self._mock_vws_api, self._base_vws_url),
            (self._mock_vwq_api, self._base_vwq_url),
        ):
            base_path = urlparse(url=base_url).path.rstrip("/")
            for route in api.routes:
                url_pattern = base_url.rstrip("/") + route.path_pattern + "$"
                compiled_url_pattern = re.compile(pattern=url_pattern)

                for http_method in route.http_methods:
                    original_callback = getattr(  # pylint: disable=bad-builtin
                        api,
                        route.route_name,
                    )
                    mock.add_callback(
                        method=http_method,
                        url=compiled_url_pattern,
                        callback=self._wrap_callback(
                            callback=original_callback,
                            delay_seconds=self._response_delay_seconds,
                            sleep_fn=self._sleep_fn,
                            base_path=base_path,
                        ),
                        content_type=None,
                    )

        if self._real_http:
            all_requests_pattern = re.compile(pattern=".*")
            mock.add_passthru(prefix=all_requests_pattern)

        self._mock = mock
        self._mock.start()

        self._router = start_respx_router(
            mock_vws_api=self._mock_vws_api,
            mock_vwq_api=self._mock_vwq_api,
            base_vws_url=self._base_vws_url,
            base_vwq_url=self._base_vwq_url,
            response_delay_seconds=self._response_delay_seconds,
            sleep_fn=self._sleep_fn,
            real_http=self._real_http,
        )

        return self

    def __exit__(self, *exc: object) -> Literal[False]:
        """Stop the Vuforia mock.

        Returns:
            False
        """
        # __exit__ needs this to be passed in but vulture thinks that it is
        # unused, so we "use" it here.
        del exc

        self._mock.stop()
        self._router.stop()
        return False
