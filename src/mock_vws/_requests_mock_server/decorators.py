"""
Decorators for using the mock.
"""

from __future__ import annotations

import re
from contextlib import ContextDecorator
from typing import TYPE_CHECKING, Literal
from urllib.parse import urljoin, urlparse

import requests
from requests_mock.mocker import Mocker

from mock_vws.query_matchers import ExactMatcher, QueryMatcher
from mock_vws.target_manager import TargetManager

from .mock_web_query_api import MockVuforiaWebQueryAPI
from .mock_web_services_api import MockVuforiaWebServicesAPI

if TYPE_CHECKING:
    from mock_vws.database import VuforiaDatabase


_EXACT_MATCHER = ExactMatcher()


class MockVWS(ContextDecorator):
    """
    Route requests to Vuforia's Web Service APIs to fakes of those APIs.
    """

    def __init__(
        self,
        base_vws_url: str = "https://vws.vuforia.com",
        base_vwq_url: str = "https://cloudreco.vuforia.com",
        match_checker: QueryMatcher = _EXACT_MATCHER,
        processing_time_seconds: int | float = 0.5,
        query_recognizes_deletion_seconds: int | float = 0.2,
        query_processes_deletion_seconds: int | float = 3,
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
            processing_time_seconds: The number of seconds
                to process each image for.
                In the real Vuforia Web Services, this is not deterministic.
            base_vwq_url: The base URL for the VWQ API.
            base_vws_url: The base URL for the VWS API.
            query_recognizes_deletion_seconds: The number
                of seconds after a target has been deleted that the query
                endpoint will still recognize the target for.
            query_processes_deletion_seconds: The number of
                seconds after a target deletion is recognized that the query
                endpoint will return a 500 response on a match.
            match_checker: A callable which takes two image values and returns
                whether they will match in a query request.

        Raises:
            requests.exceptions.MissingSchema: There is no schema in a given
                URL.
        """
        super().__init__()
        self._real_http = real_http
        self._mock: Mocker
        self._target_manager = TargetManager()

        self._base_vws_url = base_vws_url
        self._base_vwq_url = base_vwq_url
        missing_scheme_error = (
            'Invalid URL "{url}": No scheme supplied. '
            'Perhaps you meant "https://{url}".'
        )
        for url in (base_vwq_url, base_vws_url):
            result = urlparse(url)
            if not result.scheme:
                error = missing_scheme_error.format(url=url)
                raise requests.exceptions.MissingSchema(error)

        self._mock_vws_api = MockVuforiaWebServicesAPI(
            target_manager=self._target_manager,
            processing_time_seconds=processing_time_seconds,
        )

        self._mock_vwq_api = MockVuforiaWebQueryAPI(
            target_manager=self._target_manager,
            query_processes_deletion_seconds=(
                query_processes_deletion_seconds
            ),
            query_recognizes_deletion_seconds=(
                query_recognizes_deletion_seconds
            ),
            match_checker=match_checker,
        )

    def add_database(self, database: VuforiaDatabase) -> None:
        """
        Add a cloud database.

        Args:
            database: The database to add.

        Raises:
            ValueError: One of the given database keys matches a key for an
                existing database.
        """
        self._target_manager.add_database(database=database)

    def __enter__(self) -> MockVWS:
        """
        Start an instance of a Vuforia mock.

        Returns:
            ``self``.
        """
        with Mocker(real_http=self._real_http) as mock:
            for route in self._mock_vws_api.routes:
                url_pattern = urljoin(
                    base=self._base_vws_url,
                    url=route.path_pattern + "$",
                )

                for http_method in route.http_methods:
                    mock.register_uri(
                        method=http_method,
                        url=re.compile(url_pattern),
                        text=getattr(self._mock_vws_api, route.route_name),
                    )

            for route in self._mock_vwq_api.routes:
                url_pattern = urljoin(
                    base=self._base_vwq_url,
                    url=route.path_pattern + "$",
                )

                for http_method in route.http_methods:
                    mock.register_uri(
                        method=http_method,
                        url=re.compile(url_pattern),
                        text=getattr(self._mock_vwq_api, route.route_name),
                    )

        self._mock = mock
        self._mock.start()

        return self

    def __exit__(self, *exc: tuple[None, None, None]) -> Literal[False]:
        """
        Stop the Vuforia mock.

        Returns:
            False
        """
        # __exit__ needs this to be passed in but vulture thinks that it is
        # unused, so we "use" it here.
        for _ in (exc,):
            pass

        self._mock.stop()
        return False
