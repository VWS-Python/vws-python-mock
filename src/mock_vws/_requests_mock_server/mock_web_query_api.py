"""
A fake implementation of the Vuforia Web Query API.

See
https://library.vuforia.com/articles/Solution/How-To-Perform-an-Image-Recognition-Query
"""

from pathlib import Path
from typing import Any, Callable, Dict, Set, Tuple, Union

import wrapt
from requests import codes
from requests_mock import POST
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._mock_common import (
    Route,
    set_content_length_header,
    set_date_header,
)
from mock_vws._query_tools import (
    ActiveMatchingTargetsDeleteProcessing,
    MatchingTargetsWithProcessingStatus,
    get_query_match_response_text,
)
from mock_vws._query_validators import run_query_validators
from mock_vws._query_validators.exceptions import (
    AuthenticationFailure,
    AuthenticationFailureGoodFormatting,
    AuthHeaderMissing,
    BadImage,
    BoundaryNotInBody,
    ContentLengthHeaderNotInt,
    ContentLengthHeaderTooLarge,
    DateFormatNotValid,
    DateHeaderNotGiven,
    ImageNotGiven,
    InactiveProject,
    InvalidAcceptHeader,
    InvalidIncludeTargetData,
    InvalidMaxNumResults,
    MalformedAuthHeader,
    MaxNumResultsOutOfRange,
    NoBoundaryFound,
    QueryOutOfBounds,
    RequestTimeTooSkewed,
    UnknownParameters,
    UnsupportedMediaType,
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
    except DateHeaderNotGiven as exc:
        content_type = 'text/plain; charset=ISO-8859-1'
        context.headers['Content-Type'] = content_type
        context.status_code = exc.status_code
        return exc.response_text
    except (
        AuthHeaderMissing,
        DateFormatNotValid,
        MalformedAuthHeader,
    ) as exc:
        content_type = 'text/plain; charset=ISO-8859-1'
        context.headers['Content-Type'] = content_type
        context.headers['WWW-Authenticate'] = 'VWS'
        context.status_code = exc.status_code
        return exc.response_text
    except (AuthenticationFailure, AuthenticationFailureGoodFormatting) as exc:
        context.headers['WWW-Authenticate'] = 'VWS'
        context.status_code = exc.status_code
        return exc.response_text
    except (
        RequestTimeTooSkewed,
        ImageNotGiven,
        UnknownParameters,
        InactiveProject,
        InvalidIncludeTargetData,
        InvalidMaxNumResults,
        MaxNumResultsOutOfRange,
        BadImage,
    ) as exc:
        context.status_code = exc.status_code
        return exc.response_text
    except (UnsupportedMediaType, InvalidAcceptHeader) as exc:
        context.headers.pop('Content-Type')
        context.status_code = exc.status_code
        return exc.response_text
    except (NoBoundaryFound, BoundaryNotInBody) as exc:
        content_type = 'text/html;charset=UTF-8'
        context.headers['Content-Type'] = content_type
        context.status_code = exc.status_code
        return exc.response_text
    except QueryOutOfBounds as exc:
        content_type = 'text/html; charset=ISO-8859-1'
        context.headers['Content-Type'] = content_type
        cache_control = 'must-revalidate,no-cache,no-store'
        context.headers['Cache-Control'] = cache_control
        context.status_code = exc.status_code
        return exc.response_text
    except ContentLengthHeaderNotInt as exc:
        context.headers = {'Connection': 'Close'}
        context.status_code = exc.status_code
        return exc.response_text
    except ContentLengthHeaderTooLarge as exc:
        context.headers = {'Connection': 'keep-alive'}
        context.status_code = exc.status_code
        return exc.response_text

    return wrapped(*args, **kwargs)


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
            set_date_header,
            set_content_length_header,
        ]

        for decorator in decorators:
            method = decorator(method)

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
                query_processes_deletion_seconds=self.
                _query_processes_deletion_seconds,
                query_recognizes_deletion_seconds=self.
                _query_recognizes_deletion_seconds,
            )
        except (
            ActiveMatchingTargetsDeleteProcessing,
            MatchingTargetsWithProcessingStatus,
        ) as exc:
            # We return an example 500 response.
            # Each response given by Vuforia is different.
            #
            # Sometimes Vuforia will ignore matching targets with the
            # processing status, but we choose to:
            # * Do the most unexpected thing.
            # * Be consistent with every response.
            resources_dir = Path(__file__).parent.parent / 'resources'
            filename = 'match_processing_response.html'
            match_processing_resp_file = resources_dir / filename
            context.status_code = codes.INTERNAL_SERVER_ERROR
            cache_control = 'must-revalidate,no-cache,no-store'
            context.headers['Cache-Control'] = cache_control
            content_type = 'text/html; charset=ISO-8859-1'
            context.headers['Content-Type'] = content_type
            return Path(match_processing_resp_file).read_text()

        return response_text
