"""
Tests for the `Authorization` header.
"""

from textwrap import dedent
from typing import Dict, Union
from urllib.parse import urlparse

import pytest
import requests
from requests import codes
from requests.structures import CaseInsensitiveDict

from mock_vws._constants import ResultCodes
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import (
    assert_vwq_failure,
    assert_vws_failure,
)
from tests.mock_vws.utils.authorization import rfc_1123_date


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestAuthorizationHeader:
    """
    Tests for what happens when the `Authorization` header is not as expected.
    """

    def test_missing(self, endpoint: Endpoint) -> None:
        """
        An `UNAUTHORIZED` response is returned when no `Authorization` header
        is given.
        """
        date = rfc_1123_date()
        endpoint_headers = dict(endpoint.prepared_request.headers)

        headers: Dict[str, Union[str, bytes]] = {
            **endpoint_headers,
            'Date': date,
        }

        headers.pop('Authorization', None)

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(  # type: ignore
            request=endpoint.prepared_request,
        )

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
        if netloc == 'cloudreco.vuforia.com':
            assert_vwq_failure(
                response=response,
                status_code=codes.UNAUTHORIZED,
                content_type='text/plain; charset=ISO-8859-1',
            )
            assert response.text == 'Authorization header missing.'
            return

        assert_vws_failure(
            response=response,
            status_code=codes.UNAUTHORIZED,
            result_code=ResultCodes.AUTHENTICATION_FAILURE,
        )


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestMalformed:
    """
    Tests for passing a malformed ``Authorization`` header.
    """

    @pytest.mark.parametrize('authorization_string', [
        'gibberish',
        'VWS',
        'VWS ',
    ])
    def test_one_part(
        self,
        endpoint: Endpoint,
        authorization_string: str,
    ) -> None:
        """
    A valid authorization string is two "parts" when split on a space. When
    a string is given which is one "part", a ``BAD_REQUEST`` or
    ``UNAUTHORIZED`` response is returned.
        """
        date = rfc_1123_date()

        headers: Dict[str, Union[str, bytes]] = {
            **endpoint.prepared_request.headers,
            'Authorization': authorization_string,
            'Date': date,
        }

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(  # type: ignore
            request=endpoint.prepared_request,
        )

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
        if netloc == 'cloudreco.vuforia.com':
            assert_vwq_failure(
                response=response,
                status_code=codes.UNAUTHORIZED,
                content_type='text/plain; charset=ISO-8859-1',
            )
            assert response.text == 'Malformed authorization header.'
            return

        assert_vws_failure(
            response=response,
            status_code=codes.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )

    @pytest.mark.parametrize('authorization_string', [
        'VWS foobar:',
        'VWS foobar',
    ])
    def test_missing_signature(
        self,
        endpoint: Endpoint,
        authorization_string: str,
    ) -> None:
        """
        If a signature is missing `Authorization` header is given, a
        ``BAD_REQUEST`` response is given.
        """
        date = rfc_1123_date()

        headers: Dict[str, Union[str, bytes]] = {
            **endpoint.prepared_request.headers,
            'Authorization': authorization_string,
            'Date': date,
        }

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(  # type: ignore
            request=endpoint.prepared_request,
        )

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
        if netloc == 'cloudreco.vuforia.com':
            assert_vwq_failure(
                response=response,
                status_code=codes.INTERNAL_SERVER_ERROR,
                content_type='text/html; charset=ISO-8859-1',
            )
            # yapf breaks multi-line noqa, see
            # https://github.com/google/yapf/issues/524.
            # yapf: disable
            expected = dedent(
                """\
                <html>
                <head>
                <meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>
                <title>Error 500 Server Error</title>
                </head>
                <body><h2>HTTP ERROR 500</h2>
                <p>Problem accessing /v1/query. Reason:
                <pre>    Server Error</pre></p><h3>Caused by:</h3><pre>java.lang.ArrayIndexOutOfBoundsException: 1
                        at com.kooaba.queryservice.auth.KWSAuthFilter.doFilter(KWSAuthFilter.java:81)
                        at org.eclipse.jetty.servlet.ServletHandler$CachedChain.doFilter(ServletHandler.java:1652)
                        at org.eclipse.jetty.servlet.ServletHandler.doHandle(ServletHandler.java:585)
                        at org.eclipse.jetty.server.handler.ScopedHandler.handle(ScopedHandler.java:143)
                        at org.eclipse.jetty.security.SecurityHandler.handle(SecurityHandler.java:577)
                        at org.eclipse.jetty.server.session.SessionHandler.doHandle(SessionHandler.java:223)
                        at org.eclipse.jetty.server.handler.ContextHandler.doHandle(ContextHandler.java:1127)
                        at org.eclipse.jetty.servlet.ServletHandler.doScope(ServletHandler.java:515)
                        at org.eclipse.jetty.server.session.SessionHandler.doScope(SessionHandler.java:185)
                        at org.eclipse.jetty.server.handler.ContextHandler.doScope(ContextHandler.java:1061)
                        at org.eclipse.jetty.server.handler.ScopedHandler.handle(ScopedHandler.java:141)
                        at org.eclipse.jetty.server.handler.ContextHandlerCollection.handle(ContextHandlerCollection.java:215)
                        at org.eclipse.jetty.server.handler.HandlerCollection.handle(HandlerCollection.java:110)
                        at org.eclipse.jetty.server.handler.HandlerWrapper.handle(HandlerWrapper.java:97)
                        at org.eclipse.jetty.server.Server.handle(Server.java:497)
                        at org.eclipse.jetty.server.HttpChannel.handle(HttpChannel.java:310)
                        at org.eclipse.jetty.server.HttpConnection.onFillable(HttpConnection.java:257)
                        at org.eclipse.jetty.io.AbstractConnection$2.run(AbstractConnection.java:540)
                        at org.eclipse.jetty.util.thread.QueuedThreadPool.runJob(QueuedThreadPool.java:635)
                        at org.eclipse.jetty.util.thread.QueuedThreadPool$3.run(QueuedThreadPool.java:555)
                        at java.lang.Thread.run(Thread.java:748)
                </pre>
                <hr><i><small>Powered by Jetty://</small></i><hr/>

                </body>
                </html>
                """,# noqa: E501,E261
            )
            # yapf: enable
            assert response.text == expected
            return

        assert_vws_failure(
            response=response,
            status_code=codes.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )
