"""
Common utilities for creating mock routes.
"""

import cgi
import email.utils
import io
import json
from typing import Any, Callable, Dict, List, Mapping, Tuple, Union

import wrapt
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context
from requests import codes


class Route:
    """
    A container for the route details which `requests_mock` needs.

    We register routes with names, and when we have an instance to work with
    later.
    """

    route_name: str
    path_pattern: str
    http_methods: List[str]

    def __init__(
        self,
        route_name: str,
        path_pattern: str,
        http_methods: List[str],
    ) -> None:
        """
        Args:
            route_name: The name of the method.
            path_pattern: The end part of a URL pattern. E.g. `/targets` or
                `/targets/.+`.
            http_methods: HTTP methods that map to the route function.

        Attributes:
            route_name: The name of the method.
            path_pattern: The end part of a URL pattern. E.g. `/targets` or
                `/targets/.+`.
            http_methods: HTTP methods that map to the route function.
            endpoint: The method `requests_mock` should call when the endpoint
                is requested.
        """
        self.route_name = route_name
        self.path_pattern = path_pattern
        self.http_methods = http_methods


def json_dump(body: Dict[str, Any]) -> str:
    """
    Returns:
        JSON dump of data in the same way that Vuforia dumps data.
    """
    return json.dumps(obj=body, separators=(',', ':'))


@wrapt.decorator
def set_content_length_header(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Set the `Content-Length` header.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
    """
    _, context = args

    result = wrapped(*args, **kwargs)
    context.headers['Content-Length'] = str(len(result))
    return result


@wrapt.decorator
def set_date_header(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Set the `Date` header.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
    """
    _, context = args
    date = email.utils.formatdate(None, localtime=False, usegmt=True)

    result = wrapped(*args, **kwargs)
    if context.headers['Connection'] != 'Close' and context.status_code != codes.GATEWAY_TIMEOUT:
        context.headers['Date'] = date
    return result


def parse_multipart(  # pylint: disable=invalid-name
    fp: io.BytesIO,
    pdict: Mapping[str, bytes],
) -> Dict[str, List[Union[str, bytes]]]:
    """
    Return parsed ``pdict``.

    Wrapper for ``_parse_multipart`` to work around
    https://bugs.python.org/issue34226.

    See https://docs.python.org/3.8/library/cgi.html#_parse_multipart.
    """
    pdict = {
        'CONTENT-LENGTH': str(len(fp.getvalue())).encode(),
        **pdict,
    }

    return cgi.parse_multipart(fp=fp, pdict=pdict)
