"""
Decorators for using the mock.
"""

import re
from contextlib import ContextDecorator
from typing import Literal, Tuple, Union
from urllib.parse import urljoin, urlparse

import requests
from requests_mock.mocker import Mocker

from mock_vws.database import VuforiaDatabase

from .mock_web_query_api import MockVuforiaWebQueryAPI
from .mock_web_services_api import MockVuforiaWebServicesAPI


class MockVWS(ContextDecorator):
    """
    Route requests to Vuforia's Web Service APIs to fakes of those APIs.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        base_vws_url: str = 'https://vws.vuforia.com',
        base_vwq_url: str = 'https://cloudreco.vuforia.com',
        real_http: bool = False,
        processing_time_seconds: Union[int, float] = 0.5,
        query_recognizes_deletion_seconds: Union[int, float] = 0.2,
        query_processes_deletion_seconds: Union[int, float] = 3,
    ) -> None:
        """
        Route requests to Vuforia's Web Service APIs to fakes of those APIs.

        Args:
            real_http: Whether or not to forward requests to the real server if
                they are not handled by the mock.
                See
                https://requests-mock.readthedocs.io/en/latest/mocker.html#real-http-requests.
            processing_time_seconds: The number of seconds to process each
                image for. In the real Vuforia Web Services, this is not
                deterministic.
            base_vwq_url: The base URL for the VWQ API.
            base_vws_url: The base URL for the VWS API.
            query_recognizes_deletion_seconds: The number of seconds after a
                target has been deleted that the query endpoint will still
                recognize the target for.
            query_processes_deletion_seconds: The number of seconds after a
                target deletion is recognized that the query endpoint will
                return a 500 response on a match.

        Raises:
            requests.exceptions.MissingSchema: There is no schema in a given
                URL.
        """
        super().__init__()
        self._real_http = real_http
        self._mock: Mocker

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
            processing_time_seconds=processing_time_seconds,
        )

        self._mock_vwq_api = MockVuforiaWebQueryAPI(
            query_processes_deletion_seconds=(
                query_processes_deletion_seconds
            ),
            query_recognizes_deletion_seconds=(
                query_recognizes_deletion_seconds
            ),
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
        message_fmt = (
            'All {key_name}s must be unique. '
            'There is already a database with the {key_name} "{value}".'
        )
        for existing_db in self._mock_vws_api.databases:
            for existing, new, key_name in (
                (
                    existing_db.server_access_key,
                    database.server_access_key,
                    'server access key',
                ),
                (
                    existing_db.server_secret_key,
                    database.server_secret_key,
                    'server secret key',
                ),
                (
                    existing_db.client_access_key,
                    database.client_access_key,
                    'client access key',
                ),
                (
                    existing_db.client_secret_key,
                    database.client_secret_key,
                    'client secret key',
                ),
            ):
                if existing == new:
                    message = message_fmt.format(key_name=key_name, value=new)
                    raise ValueError(message)

        self._mock_vws_api.databases.add(database)
        self._mock_vwq_api.databases.add(database)

    def __enter__(self) -> 'MockVWS':
        """
        Start an instance of a Vuforia mock.

        Returns:
            ``self``.
        """

        with Mocker(real_http=self._real_http) as mock:
            for route in self._mock_vws_api.routes:
                url_pattern = urljoin(
                    base=self._base_vws_url,
                    url=route.path_pattern + '$',
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
                    url=route.path_pattern + '$',
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

    def __exit__(self, *exc: Tuple[None, None, None]) -> Literal[False]:
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
