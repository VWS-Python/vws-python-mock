"""
Decorators for using the mock.
"""

from __future__ import annotations

import re
from contextlib import ContextDecorator
from typing import TYPE_CHECKING, Literal, Protocol
from urllib.parse import urljoin, urlparse

import requests
from requests_mock.mocker import Mocker

from mock_vws.image_matchers import (
    AverageHashMatcher,
    ImageMatcher,
)
from mock_vws.target_manager import TargetManager
from mock_vws.target_raters import BrisqueTargetTrackingRater

from .mock_web_query_api import MockVuforiaWebQueryAPI
from .mock_web_services_api import MockVuforiaWebServicesAPI

if TYPE_CHECKING:
    from mock_vws.database import VuforiaDatabase
    from mock_vws.target_raters import TargetTrackingRater


_AVERAGE_HASH_MATCHER = AverageHashMatcher(threshold=10)
_BRISQUE_TRACKING_RATER = BrisqueTargetTrackingRater()


# TODO: Make backends choosable by users
# TODO: Make a backend for Docker
#   - Be careful with real_http
# TODO: Make a backend for real Vuforia
#   - Be careful with real_http
# TODO: Use the Docker backend in VWS-Python timeout tests
# TODO: Use backends in fixtures for e.g. --skip-real


class _MockBackend(Protocol):
    def __init__(self) -> None:
        ...

    def add_database(self, database: VuforiaDatabase) -> None:
        ...

    def start(
        self,
        base_vws_url: str,
        base_vwq_url: str,
        duplicate_match_checker: ImageMatcher,
        query_match_checker: ImageMatcher,
        processing_time_seconds: int | float,
        query_recognizes_deletion_seconds: int | float,
        query_processes_deletion_seconds: int | float,
        target_tracking_rater: TargetTrackingRater,
        *,
        real_http: bool,
    ) -> None:
        ...

    def stop(self) -> None:
        ...


class _RequestsMockBackend:
    def __init__(self) -> None:
        self._mock: Mocker
        self._target_manager = TargetManager()

    def add_database(self, database: VuforiaDatabase) -> None:
        self._target_manager.add_database(database=database)

    def start(
        self,
        base_vws_url: str,
        base_vwq_url: str,
        duplicate_match_checker: ImageMatcher,
        query_match_checker: ImageMatcher,
        processing_time_seconds: int | float,
        query_recognizes_deletion_seconds: int | float,
        query_processes_deletion_seconds: int | float,
        target_tracking_rater: TargetTrackingRater,
        *,
        real_http: bool,
    ) -> None:
        mock_vws_api = MockVuforiaWebServicesAPI(
            target_manager=self._target_manager,
            processing_time_seconds=processing_time_seconds,
            duplicate_match_checker=duplicate_match_checker,
            target_tracking_rater=target_tracking_rater,
        )

        mock_vwq_api = MockVuforiaWebQueryAPI(
            target_manager=self._target_manager,
            query_processes_deletion_seconds=(
                query_processes_deletion_seconds
            ),
            query_recognizes_deletion_seconds=(
                query_recognizes_deletion_seconds
            ),
            query_match_checker=query_match_checker,
        )

        with Mocker(real_http=real_http) as mock:
            for vws_route in mock_vws_api.routes:
                url_pattern = urljoin(
                    base=base_vws_url,
                    url=f"{vws_route.path_pattern}$",
                )

                for vws_http_method in vws_route.http_methods:
                    mock.register_uri(
                        method=vws_http_method,
                        url=re.compile(url_pattern),
                        text=getattr(mock_vws_api, vws_route.route_name),
                    )

            for vwq_route in mock_vwq_api.routes:
                url_pattern = urljoin(
                    base=base_vwq_url,
                    url=f"{vwq_route.path_pattern}$",
                )

                for vwq_http_method in vwq_route.http_methods:
                    mock.register_uri(
                        method=vwq_http_method,
                        url=re.compile(url_pattern),
                        text=getattr(mock_vwq_api, vwq_route.route_name),
                    )

        self._mock = mock
        self._mock.start()

    def stop(self) -> None:
        self._mock.stop()


class MockVWS(ContextDecorator):
    """
    Route requests to Vuforia's Web Service APIs to fakes of those APIs.
    """

    def __init__(
        self,
        base_vws_url: str = "https://vws.vuforia.com",
        base_vwq_url: str = "https://cloudreco.vuforia.com",
        duplicate_match_checker: ImageMatcher = _AVERAGE_HASH_MATCHER,
        query_match_checker: ImageMatcher = _AVERAGE_HASH_MATCHER,
        processing_time_seconds: int | float = 2,
        query_recognizes_deletion_seconds: int | float = 2,
        query_processes_deletion_seconds: int | float = 3,
        target_tracking_rater: TargetTrackingRater = _BRISQUE_TRACKING_RATER,
        mock_backend: type[_MockBackend] = _RequestsMockBackend,
        *,
        real_http: bool = False,
    ) -> None:
        """
        Route requests to Vuforia's Web Service APIs to fakes of those APIs.

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
            query_recognizes_deletion_seconds: The number
                of seconds after a target has been deleted that the query
                endpoint will still recognize the target for.
            query_processes_deletion_seconds: The number of
                seconds after a target deletion is recognized that the query
                endpoint will return a 500 response on a match.
            query_match_checker: A callable which takes two image values and
                returns whether they will match in a query request.
            duplicate_match_checker: A callable which takes two image values
                and returns whether they are duplicates.
            target_tracking_rater: A callable for rating targets for tracking.

        Raises:
            requests.exceptions.MissingSchema: There is no schema in a given
                URL.
        """
        super().__init__()
        self._backend = mock_backend()

        self._base_vws_url = base_vws_url
        self._base_vwq_url = base_vwq_url
        self._duplicate_match_checker = duplicate_match_checker
        self._query_match_checker = query_match_checker
        self._processing_time_seconds = processing_time_seconds
        self._query_recognizes_deletion_seconds = (
            query_recognizes_deletion_seconds
        )
        self._query_processes_deletion_seconds = (
            query_processes_deletion_seconds
        )
        self._target_tracking_rater = target_tracking_rater
        self._real_http = real_http

        missing_scheme_error = (
            'Invalid URL "{url}": No scheme supplied. '
            'Perhaps you meant "https://{url}".'
        )
        for url in (base_vwq_url, base_vws_url):
            parse_result = urlparse(url=url)
            if not parse_result.scheme:
                error = missing_scheme_error.format(url=url)
                raise requests.exceptions.MissingSchema(error)

    def add_database(self, database: VuforiaDatabase) -> None:
        """
        Add a cloud database.

        Args:
            database: The database to add.

        Raises:
            ValueError: One of the given database keys matches a key for an
                existing database.
        """
        self._backend.add_database(database=database)

    def __enter__(self) -> MockVWS:
        """
        Start an instance of a Vuforia mock.

        Returns:
            ``self``.
        """
        self._backend.start(
            base_vws_url=self._base_vws_url,
            base_vwq_url=self._base_vwq_url,
            duplicate_match_checker=self._duplicate_match_checker,
            query_match_checker=self._query_match_checker,
            processing_time_seconds=self._processing_time_seconds,
            query_recognizes_deletion_seconds=self._query_recognizes_deletion_seconds,
            query_processes_deletion_seconds=self._query_processes_deletion_seconds,
            target_tracking_rater=self._target_tracking_rater,
            real_http=self._real_http,
        )
        return self

    def __exit__(self, *exc: tuple[None, None, None]) -> Literal[False]:
        """
        Stop the Vuforia mock.

        Returns:
            False
        """
        # __exit__ needs this to be passed in but vulture thinks that it is
        # unused, so we "use" it here.
        assert isinstance(exc, tuple)
        self._backend.stop()
        return False
