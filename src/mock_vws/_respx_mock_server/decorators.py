"""Decorators for using the mock with httpx via respx."""

import re
import time
from collections.abc import Callable, Mapping
from contextlib import ContextDecorator
from typing import Literal, Self
from urllib.parse import urljoin, urlparse

import httpx
import respx
from beartype import BeartypeConf, beartype
from requests import PreparedRequest
from requests.structures import CaseInsensitiveDict

from mock_vws._requests_mock_server.decorators import MissingSchemeError
from mock_vws._requests_mock_server.mock_web_query_api import (
    MockVuforiaWebQueryAPI,
)
from mock_vws._requests_mock_server.mock_web_services_api import (
    MockVuforiaWebServicesAPI,
)
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.image_matchers import (
    ImageMatcher,
    StructuralSimilarityMatcher,
)
from mock_vws.target_manager import TargetManager
from mock_vws.target_raters import (
    BrisqueTargetTrackingRater,
    TargetTrackingRater,
)

_ResponseType = tuple[int, Mapping[str, str], str | bytes]

_STRUCTURAL_SIMILARITY_MATCHER = StructuralSimilarityMatcher()
_BRISQUE_TRACKING_RATER = BrisqueTargetTrackingRater()


def _to_prepared_request(request: httpx.Request) -> PreparedRequest:
    """Convert an httpx.Request to a requests.PreparedRequest.

    Args:
        request: The httpx request to convert.

    Returns:
        A PreparedRequest with headers, body, method, and url set.
        The ``path_url`` property is derived automatically from ``url``.
    """
    prepared = PreparedRequest()
    prepared.method = request.method
    prepared.url = str(request.url)  # type: ignore[arg-type]
    prepared.headers = CaseInsensitiveDict(  # type: ignore[arg-type]
        dict(request.headers)
    )
    prepared.body = request.content
    return prepared


@beartype(conf=BeartypeConf(is_pep484_tower=True))
class MockVWSForHttpx(ContextDecorator):
    """Route httpx requests to Vuforia's Web Service APIs to fakes of those
    APIs.
    """

    def __init__(
        self,
        *,
        base_vws_url: str = "https://vws.vuforia.com",
        base_vwq_url: str = "https://cloudreco.vuforia.com",
        duplicate_match_checker: ImageMatcher = _STRUCTURAL_SIMILARITY_MATCHER,
        query_match_checker: ImageMatcher = _STRUCTURAL_SIMILARITY_MATCHER,
        processing_time_seconds: float = 2.0,
        target_tracking_rater: TargetTrackingRater = _BRISQUE_TRACKING_RATER,
        real_http: bool = False,
        response_delay_seconds: float = 0.0,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        """Route httpx requests to Vuforia's Web Service APIs to fakes of
        those APIs.

        Args:
            real_http: Whether or not to forward requests to the real
                server if they are not handled by the mock.
            processing_time_seconds: The number of seconds to process each
                image for.
                In the real Vuforia Web Services, this is not deterministic.
            base_vwq_url: The base URL for the VWQ API.
            base_vws_url: The base URL for the VWS API.
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
        """
        super().__init__()
        self._real_http = real_http
        self._response_delay_seconds = response_delay_seconds
        self._sleep_fn = sleep_fn
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
            duplicate_match_checker=duplicate_match_checker,
            target_tracking_rater=target_tracking_rater,
        )

        self._mock_vwq_api = MockVuforiaWebQueryAPI(
            target_manager=self._target_manager,
            query_match_checker=query_match_checker,
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

    def _make_callback(
        self,
        handler: Callable[[PreparedRequest], _ResponseType],
    ) -> Callable[[httpx.Request], httpx.Response]:
        """Create a respx-compatible callback from a handler.

        Args:
            handler: A handler that takes a PreparedRequest and returns a
                response tuple.

        Returns:
            A callback that takes an httpx.Request and returns an
            httpx.Response.
        """
        delay_seconds = self._response_delay_seconds
        sleep_fn = self._sleep_fn

        def callback(request: httpx.Request) -> httpx.Response:
            """Handle an httpx request by converting it and calling the
            handler.

            Args:
                request: The httpx request to handle.

            Returns:
                An httpx.Response built from the handler's return value.

            Raises:
                httpx.ReadTimeout: The response delay exceeded the read
                    timeout.
            """
            prepared = _to_prepared_request(request=request)
            timeout_info: dict[str, float | None] = request.extensions.get(
                "timeout", {}
            )
            read_timeout = timeout_info.get("read")
            if read_timeout is not None and delay_seconds > read_timeout:
                sleep_fn(read_timeout)
                raise httpx.ReadTimeout(
                    message="Response delay exceeded read timeout",
                    request=request,
                )
            status_code, headers, body = handler(prepared)
            sleep_fn(delay_seconds)
            if isinstance(body, str):
                body = body.encode()
            return httpx.Response(
                status_code=status_code,
                headers=list(headers.items()),
                content=body,
            )

        return callback

    @staticmethod
    def _block_unmatched(request: httpx.Request) -> httpx.Response:
        """Raise ConnectError for unmatched requests when real_http=False.

        Args:
            request: The unmatched httpx request.

        Raises:
            httpx.ConnectError: Always raised to block unmatched requests.
        """
        raise httpx.ConnectError(
            message="Connection refused by mock",
            request=request,
        )

    def __enter__(self) -> Self:
        """Start an instance of a Vuforia mock.

        Returns:
            ``self``.
        """
        router = respx.MockRouter(
            assert_all_called=False,
            assert_all_mocked=False,
        )

        for api, base_url in (
            (self._mock_vws_api, self._base_vws_url),
            (self._mock_vwq_api, self._base_vwq_url),
        ):
            for route in api.routes:
                url_pattern = urljoin(
                    base=base_url,
                    url=f"{route.path_pattern}$",
                )
                compiled_url_pattern = re.compile(pattern=url_pattern)

                for http_method in route.http_methods:
                    original_callback = getattr(api, route.route_name)
                    router.route(
                        method=http_method,
                        url=compiled_url_pattern,
                    ).mock(
                        side_effect=self._make_callback(
                            handler=original_callback,
                        ),
                    )

        if self._real_http:
            router.route().pass_through()
        else:
            router.route().mock(side_effect=self._block_unmatched)

        router.start()
        self._router = router
        return self

    def __exit__(self, *exc: object) -> Literal[False]:
        """Stop the Vuforia mock.

        Returns:
            False
        """
        del exc
        self._router.stop()
        return False
