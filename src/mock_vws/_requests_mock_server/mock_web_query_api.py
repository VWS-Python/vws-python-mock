"""
A fake implementation of the Vuforia Web Query API.

See
https://developer.vuforia.com/library/web-api/vuforia-query-web-api
"""

from __future__ import annotations

import email.utils
from http import HTTPMethod
from typing import TYPE_CHECKING

from mock_vws._mock_common import Route
from mock_vws._query_tools import (
    get_query_match_response_text,
)
from mock_vws._query_validators import run_query_validators
from mock_vws._query_validators.exceptions import (
    ValidatorError,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from requests_mock.request import Request
    from requests_mock.response import Context

    from mock_vws.image_matchers import ImageMatcher
    from mock_vws.target_manager import TargetManager

_ROUTES: set[Route] = set()


def route(
    path_pattern: str,
    http_methods: set[str],
) -> Callable[[Callable[..., str]], Callable[..., str]]:
    """
    Register a decorated method so that it can be recognized as a route.

    Args:
        path_pattern: The end part of a URL pattern. E.g. `/targets` or
            `/targets/.+`.
        http_methods: HTTP methods that map to the route function.

    Returns:
        A decorator which takes methods and makes them recognizable as routes.
    """

    def decorator(method: Callable[..., str]) -> Callable[..., str]:
        """
        Register a decorated method so that it can be recognized as a route.

        Returns:
            The given `method` with multiple changes, including added
            validators.
        """
        _ROUTES.add(
            Route(
                route_name=method.__name__,
                path_pattern=path_pattern,
                http_methods=frozenset(http_methods),
            ),
        )

        return method

    return decorator


def _body_bytes(request: Request) -> bytes:
    """
    Return the body of a request as bytes.
    """
    if request.body is None:
        return b""

    if isinstance(request.body, str):
        return request.body.encode(encoding="utf-8")

    assert isinstance(request.body, bytes)
    return request.body


class MockVuforiaWebQueryAPI:
    """
    A fake implementation of the Vuforia Web Query API.

    This implementation is tied to the implementation of `requests_mock`.
    """

    def __init__(
        self,
        target_manager: TargetManager,
        query_match_checker: ImageMatcher,
    ) -> None:
        """
        Args:
            target_manager: The target manager which holds all databases.
            query_match_checker: A callable which takes two image values and
                returns whether they match.

        Attributes:
            routes: The `Route`s to be used in the mock.
        """
        self.routes: set[Route] = _ROUTES
        self._target_manager = target_manager
        self._query_match_checker = query_match_checker

    @route(path_pattern="/v1/query", http_methods={HTTPMethod.POST})
    def query(self, request: Request, context: Context) -> str:
        """
        Perform an image recognition query.
        """
        try:
            run_query_validators(
                request_path=request.path,
                request_headers=request.headers,
                request_body=_body_bytes(request=request),
                request_method=request.method,
                databases=self._target_manager.databases,
            )
        except ValidatorError as exc:
            context.headers = exc.headers
            context.status_code = exc.status_code
            return exc.response_text

        response_text = get_query_match_response_text(
            request_headers=request.headers,
            request_body=_body_bytes(request=request),
            request_method=request.method,
            request_path=request.path,
            databases=self._target_manager.databases,
            query_match_checker=self._query_match_checker,
        )

        date = email.utils.formatdate(
            timeval=None,
            localtime=False,
            usegmt=True,
        )
        context.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Server": "nginx",
            "Date": date,
            "Content-Length": str(len(response_text)),
        }
        return response_text
