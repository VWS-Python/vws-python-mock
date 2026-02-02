"""Decorators for using the mock."""

import re
import threading
import time
from contextlib import ContextDecorator
from typing import TYPE_CHECKING, Any, Literal, Self
from urllib.parse import urljoin, urlparse

import requests as requests_lib
from beartype import BeartypeConf, beartype
from responses import RequestsMock

from mock_vws.database import VuforiaDatabase
from mock_vws.image_matchers import (
    ImageMatcher,
    StructuralSimilarityMatcher,
)
from mock_vws.target_manager import TargetManager
from mock_vws.target_raters import (
    BrisqueTargetTrackingRater,
    TargetTrackingRater,
)

from .mock_web_query_api import MockVuforiaWebQueryAPI
from .mock_web_services_api import MockVuforiaWebServicesAPI

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from requests import PreparedRequest
    from requests.adapters import HTTPAdapter  # noqa: F401

    ResponseType = tuple[int, Mapping[str, str], str]
    Callback = Callable[[PreparedRequest], ResponseType]  # noqa: F841

# Thread-local storage to capture the request timeout
_timeout_storage = threading.local()

_STRUCTURAL_SIMILARITY_MATCHER = StructuralSimilarityMatcher()
_BRISQUE_TRACKING_RATER = BrisqueTargetTrackingRater()


class MissingSchemeError(Exception):
    """Raised when a URL is missing a schema."""

    def __init__(self, url: str) -> None:
        """
        Args:
            url: The URL which is missing a scheme.
        """
        super().__init__()
        self.url = url

    def __str__(self) -> str:
        """
        Give a string representation of this error with a
        suggestion.
        """
        return (
            f'Invalid URL "{self.url}": No scheme supplied. '
            f'Perhaps you meant "https://{self.url}".'
        )


@beartype(conf=BeartypeConf(is_pep484_tower=True))
class MockVWS(ContextDecorator):
    """Route requests to Vuforia's Web Service APIs to fakes of those APIs."""

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
    ) -> None:
        """Route requests to Vuforia's Web Service APIs to fakes of those
        APIs.

        Args:
            real_http: Whether or not to forward requests to the real
                server if they are not handled by the mock.
                See
                https://requests-mock.readthedocs.io/en/latest/mocker.html#real-http-requests.
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

        Raises:
            MissingSchemeError: There is no scheme in a given URL.
        """
        super().__init__()
        self._real_http = real_http
        self._response_delay_seconds = response_delay_seconds
        self._mock: RequestsMock
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

    def add_database(self, database: VuforiaDatabase) -> None:
        """Add a cloud database.

        Args:
            database: The database to add.

        Raises:
            ValueError: One of the given database keys matches a key for an
                existing database.
        """
        self._target_manager.add_database(database=database)

    def __enter__(self) -> Self:
        """Start an instance of a Vuforia mock.

        Returns:
            ``self``.
        """
        compiled_url_patterns: Iterable[re.Pattern[str]] = set()
        delay_seconds = self._response_delay_seconds

        def wrap_callback(callback: "Callback") -> "Callback":
            """Wrap a callback to add a response delay."""

            def wrapped(request: "PreparedRequest") -> "ResponseType":
                # Check if the delay would exceed the request timeout
                timeout = getattr(_timeout_storage, "timeout", None)
                if timeout is not None and delay_seconds > 0:
                    # timeout can be a float or a tuple (connect, read)
                    if isinstance(timeout, tuple):
                        effective_timeout: float | None = timeout[1]  # read timeout
                    else:
                        effective_timeout = timeout
                    if (
                        effective_timeout is not None
                        and delay_seconds > effective_timeout
                    ):
                        raise requests_lib.exceptions.Timeout

                result = callback(request)
                time.sleep(delay_seconds)
                return result

            return wrapped

        mock = RequestsMock(assert_all_requests_are_fired=False)

        # Patch _on_request to capture the timeout parameter
        original_on_request = mock._on_request  # noqa: SLF001

        def patched_on_request(
            adapter: "HTTPAdapter",
            request: "PreparedRequest",
            **kwargs: Any,  # noqa: ANN401
        ) -> Any:  # noqa: ANN401
            _timeout_storage.timeout = kwargs.get("timeout")
            return original_on_request(adapter, request, **kwargs)  # type: ignore[misc]

        mock._on_request = patched_on_request  # type: ignore[method-assign]  # noqa: SLF001
        for vws_route in self._mock_vws_api.routes:
            url_pattern = urljoin(
                base=self._base_vws_url,
                url=f"{vws_route.path_pattern}$",
            )
            compiled_url_pattern = re.compile(pattern=url_pattern)
            compiled_url_patterns = {
                *compiled_url_patterns,
                compiled_url_pattern,
            }

            for vws_http_method in vws_route.http_methods:
                original_callback = getattr(
                    self._mock_vws_api, vws_route.route_name
                )
                mock.add_callback(
                    method=vws_http_method,
                    url=compiled_url_pattern,
                    callback=wrap_callback(callback=original_callback),
                    content_type=None,
                )

        for vwq_route in self._mock_vwq_api.routes:
            url_pattern = urljoin(
                base=self._base_vwq_url,
                url=f"{vwq_route.path_pattern}$",
            )
            compiled_url_pattern = re.compile(pattern=url_pattern)
            compiled_url_patterns = {
                *compiled_url_patterns,
                compiled_url_pattern,
            }

            for vwq_http_method in vwq_route.http_methods:
                original_callback = getattr(
                    self._mock_vwq_api, vwq_route.route_name
                )
                mock.add_callback(
                    method=vwq_http_method,
                    url=compiled_url_pattern,
                    callback=wrap_callback(callback=original_callback),
                    content_type=None,
                )

        if self._real_http:
            all_requests_pattern = re.compile(pattern=".*")
            mock.add_passthru(prefix=all_requests_pattern)

        self._mock = mock
        self._mock.start()

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
        return False
