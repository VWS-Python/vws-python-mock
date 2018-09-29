"""
Decorators for using the mock.
"""

import email.utils
import re
from contextlib import ContextDecorator
from typing import Tuple, Union
from urllib.parse import urljoin

from requests_mock.mocker import Mocker

from mock_vws.database import VuforiaDatabase

from ._mock_web_query_api import MockVuforiaWebQueryAPI
from ._mock_web_services_api import MockVuforiaWebServicesAPI


class MockVWS(ContextDecorator):
    """
    Route requests to Vuforia's Web Service APIs to fakes of those APIs.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        database: VuforiaDatabase,
        base_vws_url: str = 'https://vws.vuforia.com',
        base_vwq_url: str = 'https://cloudreco.vuforia.com',
        real_http: bool=False,
        processing_time_seconds: Union[int, float]=0.5,
        query_recognizes_deletion_seconds: Union[int, float]=3,
    ) -> None:
        """
        Route requests to Vuforia's Web Service APIs to fakes of those APIs.

        Connecting to the Vuforia Web Services requires an access key and a
        secret key.  The mock also requires these keys as it provides realistic
        authentication support.

        By default, the mock uses random strings as the access and secret keys.

        The mock does not check whether the access and secret keys are valid.
        It only checks whether the keys used to set up the mock instance match
        those used to create requests.

        Args:
            real_http: Whether or not to forward requests to the real server if
                they are not handled by the mock.
                See
                http://requests-mock.readthedocs.io/en/latest/mocker.html#real-http-requests.
            database: A Vuforia database.
            processing_time_seconds: The number of seconds to process each
                image for. In the real Vuforia Web Services, this is not
                deterministic.
            base_vwq_url: The base URL for the VWQ API.
            base_vws_url: The base URL for the VWS API.
            query_recognizes_deletion_seconds: The number of seconds after a
                target has been deleted that the query endpoint will return a
                500 response for on a match.

        Attributes:
            client_access_key (str): A VWS client access key for the mock.
            client_secret_key (str): A VWS client secret key for the mock.
            server_access_key (str): A VWS server access key for the mock.
            server_secret_key (str): A VWS server secret key for the mock.
            database_name (str): The name of the mock VWS target manager
                database.
        """
        super().__init__()
        self._real_http = real_http
        self._mock = Mocker()

        self._database = database

        self.server_access_key = self._database.server_access_key.decode()
        self.server_secret_key = self._database.server_secret_key.decode()
        self.client_access_key = self._database.client_access_key.decode()
        self.client_secret_key = self._database.client_secret_key.decode()
        self.database_name = self._database.database_name

        self._base_vws_url = base_vws_url
        self._base_vwq_url = base_vwq_url

        self._mock_vws_api = MockVuforiaWebServicesAPI(
            processing_time_seconds=processing_time_seconds,
        )

        self._mock_vwq_api = MockVuforiaWebQueryAPI(
            query_recognizes_deletion_seconds=(
                query_recognizes_deletion_seconds
            ),
        )

    def _add_database(self, database: VuforiaDatabase) -> None:
        """
        Add a cloud database.

        Args:
            database: The database to add.
        """
        self._mock_vws_api.databases.append(database)
        self._mock_vwq_api.databases.append(database)

    def __enter__(self) -> 'MockVWS':
        """
        Start an instance of a Vuforia mock with access keys set from
        environment variables.

        Returns:
            ``self``.
        """

        date = email.utils.formatdate(None, localtime=False, usegmt=True)

        headers = {
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Server': 'nginx',
            'Date': date,
        }

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
                        headers=headers,
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
                        headers=headers,
                    )

        self._mock = mock
        self._mock.start()
        self._add_database(database=self._database)

        return self

    def __exit__(self, *exc: Tuple[None, None, None]) -> bool:
        """
        Stop the Vuforia mock.

        Returns:
            False
        """
        # __exit__ needs this to be passed in but vulture thinks that it is
        # unused, so we "use" it here.
        for _ in (exc, ):
            pass

        self._mock.stop()
        return False
