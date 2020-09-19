"""
A fake implementation of the Vuforia Web Query API.

See
https://library.vuforia.com/articles/Solution/How-To-Perform-an-Image-Recognition-Query
"""

import email.utils
from typing import Any, Callable, Dict, Set, Tuple, Union

import wrapt
from requests_mock import POST
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._mock_common import Route, set_content_length_header
from mock_vws._query_tools import (
    ActiveMatchingTargetsDeleteProcessing,
    MatchingTargetsWithProcessingStatus,
    get_query_match_response_text,
)
from mock_vws._query_validators import run_query_validators
from mock_vws._query_validators.exceptions import (
    MatchProcessing,
    ValidatorException,
)
from mock_vws.database import VuforiaDatabase

ROUTES = set([])


@wrapt.decorator
def run_validators(
    wrapped: Callable[..., str],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Run all validators for the query endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
    """
    request, context = args
    try:
        run_query_validators(
            request_path=request.path,
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            databases=instance.databases,
        )
        return wrapped(*args, **kwargs)
    except ValidatorException as exc:
        context.headers = exc.headers
        context.status_code = exc.status_code
        return exc.response_text


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

        decorators = [
            run_validators,
            set_content_length_header,
        ]

        for decorator in decorators:
            # See https://github.com/PyCQA/pylint/issues/259
            method = decorator(  # pylint: disable=no-value-for-parameter
                method,
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
        query_recognizes_deletion_seconds: Union[int, float],
        query_processes_deletion_seconds: Union[int, float],
    ) -> None:
        """
        Args:
            query_recognizes_deletion_seconds: The number of seconds after a
                target has been deleted that the query endpoint will still
                recognize the target for.
            query_processes_deletion_seconds: The number of seconds after a
                target deletion is recognized that the query endpoint will
                return a 500 response on a match.

        Attributes:
            routes: The `Route`s to be used in the mock.
            databases: Target databases.
        """
        self.routes: Set[Route] = ROUTES
        self.databases: Set[VuforiaDatabase] = set([])
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
            response_text = get_query_match_response_text(
                request_headers=request.headers,
                request_body=request.body,
                request_method=request.method,
                request_path=request.path,
                databases=self.databases,
                query_processes_deletion_seconds=(
                    self._query_processes_deletion_seconds
                ),
                query_recognizes_deletion_seconds=(
                    self._query_recognizes_deletion_seconds
                ),
            )
        except (
            ActiveMatchingTargetsDeleteProcessing,
            MatchingTargetsWithProcessingStatus,
        ) as exc:
            raise MatchProcessing from exc

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        context.headers = {
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Server': 'nginx',
            'Date': date,
        }
        return response_text
