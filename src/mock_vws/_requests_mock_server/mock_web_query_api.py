"""
A fake implementation of the Vuforia Web Query API.

See
https://library.vuforia.com/articles/Solution/How-To-Perform-an-Image-Recognition-Query
"""

from __future__ import annotations

import email.utils
from typing import Callable, Set

from requests_mock import POST
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._mock_common import Route
from mock_vws._query_tools import (
    ActiveMatchingTargetsDeleteProcessing,
    get_query_match_response_text,
)
from mock_vws._query_validators import run_query_validators
from mock_vws._query_validators.exceptions import (
    DeletedTargetMatched,
    ValidatorException,
)
from mock_vws.target_manager import TargetManager

ROUTES = set()


def route(
    path_pattern: str,
    http_methods: Set[str],
) -> Callable[..., Callable]:
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
        ROUTES.add(
            Route(
                route_name=method.__name__,
                path_pattern=path_pattern,
                http_methods=frozenset(http_methods),
            ),
        )

        return method

    return decorator


class MockVuforiaWebQueryAPI:
    """
    A fake implementation of the Vuforia Web Query API.

    This implementation is tied to the implementation of `requests_mock`.
    """

    def __init__(
        self,
        target_manager: TargetManager,
        query_recognizes_deletion_seconds: int | float,
        query_processes_deletion_seconds: int | float,
    ) -> None:
        """
        Args:
            target_manager: The target manager which holds all databases.
            query_recognizes_deletion_seconds: The number of seconds after a
                target has been deleted that the query endpoint will still
                recognize the target for.
            query_processes_deletion_seconds: The number of seconds after a
                target deletion is recognized that the query endpoint will
                return a 500 response on a match.

        Attributes:
            routes: The `Route`s to be used in the mock.
        """
        self.routes: Set[Route] = ROUTES
        self._target_manager = target_manager
        self._query_processes_deletion_seconds = (
            query_processes_deletion_seconds
        )
        self._query_recognizes_deletion_seconds = (
            query_recognizes_deletion_seconds
        )

    @route(path_pattern='/v1/query', http_methods={POST})
    def query(
        self,
        request: _RequestObjectProxy,
        context: _Context,
    ) -> str:
        """
        Perform an image recognition query.
        """
        try:
            run_query_validators(
                request_path=request.path,
                request_headers=request.headers,
                request_body=request.body,
                request_method=request.method,
                databases=self._target_manager.databases,
            )
        except ValidatorException as exc:
            context.headers = exc.headers
            context.status_code = exc.status_code
            return exc.response_text

        try:
            response_text = get_query_match_response_text(
                request_headers=request.headers,
                request_body=request.body,
                request_method=request.method,
                request_path=request.path,
                databases=self._target_manager.databases,
                query_processes_deletion_seconds=(
                    self._query_processes_deletion_seconds
                ),
                query_recognizes_deletion_seconds=(
                    self._query_recognizes_deletion_seconds
                ),
            )
        except ActiveMatchingTargetsDeleteProcessing:
            deleted_target_matched_exception = DeletedTargetMatched()
            context.headers = deleted_target_matched_exception.headers
            context.status_code = deleted_target_matched_exception.status_code
            return deleted_target_matched_exception.response_text

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        context.headers = {
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Server': 'nginx',
            'Date': date,
            'Content-Length': str(len(response_text)),
        }
        return response_text
