import copy
import email.utils
from http import HTTPStatus
from typing import Dict, Optional

import requests
from flask import Flask, Response, request
from werkzeug.datastructures import Headers

from mock_vws._query_tools import (  # TODO remove each of these and just raise the validator exception
    ActiveMatchingTargetsDeleteProcessing,
    MatchingTargetsWithProcessingStatus,
    get_query_match_response_text,
)
from mock_vws._query_validators import run_query_validators
from mock_vws._query_validators.exceptions import (
    MatchProcessing,
    ValidatorException,
)

from ..vws._databases import get_all_databases

CLOUDRECO_FLASK_APP = Flask(import_name=__name__)
CLOUDRECO_FLASK_APP.config['PROPAGATE_EXCEPTIONS'] = True


@CLOUDRECO_FLASK_APP.before_request
def validate_request() -> None:
    request.environ['wsgi.input_terminated'] = True
    input_stream_copy = copy.copy(request.input_stream)
    request_body = input_stream_copy.read()
    databases = get_all_databases()
    run_query_validators(
        request_headers=dict(request.headers),
        request_body=request_body,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )


class ResponseNoContentTypeAdded(Response):
    """
    A custom response type.

    Without this, a content type is added to all responses.
    Some of our responses need to not have a "Content-Type" header.
    """

    def __init__(
        self,
        response: Optional[str] = None,
        status: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
        mimetype: Optional[str] = None,
        content_type: Optional[str] = None,
        direct_passthrough: bool = False,
    ) -> None:
        if headers:
            content_type_from_headers = headers.get('Content-Type')
        else:
            content_type_from_headers = None

        super().__init__(
            response=response,
            status=status,
            headers=headers,
            mimetype=mimetype,
            content_type=content_type,
            direct_passthrough=direct_passthrough,
        )

        if (
            content_type is None
            and self.headers
            and 'Content-Type' in self.headers
            and not content_type_from_headers
        ):
            headers_dict = dict(self.headers)
            headers_dict.pop('Content-Type')
            self.headers = Headers(headers_dict)


CLOUDRECO_FLASK_APP.response_class = ResponseNoContentTypeAdded


@CLOUDRECO_FLASK_APP.errorhandler(requests.exceptions.ConnectionError)
def handle_connection_error(
    exc: requests.exceptions.ConnectionError,
) -> Response:
    # TODO: Issue
    # This is incorrect - it raises on the server but should raise on the
    # client
    # Look into how ``requests`` handles it
    raise exc


@CLOUDRECO_FLASK_APP.errorhandler(ValidatorException)
def handle_exceptions(exc: ValidatorException) -> Response:
    """
    Return the error response associated with the given exception.
    """
    return ResponseNoContentTypeAdded(
        status=exc.status_code.value,
        response=exc.response_text,
        headers=exc.headers,
    )


@CLOUDRECO_FLASK_APP.route('/v1/query', methods=['POST'])
def query() -> Response:
    """
    Perform an image recognition query.
    """
    # TODO these should be configurable
    query_processes_deletion_seconds = 0.2
    query_recognizes_deletion_seconds = 0.2
    databases = get_all_databases()
    input_stream_copy = copy.copy(request.input_stream)
    request_body = input_stream_copy.read()
    date = email.utils.formatdate(None, localtime=False, usegmt=True)

    try:
        response_text = get_query_match_response_text(
            request_headers=dict(request.headers),
            request_body=request_body,
            request_method=request.method,
            request_path=request.path,
            databases=databases,
            query_processes_deletion_seconds=query_processes_deletion_seconds,
            query_recognizes_deletion_seconds=query_recognizes_deletion_seconds,
        )
    except (
        ActiveMatchingTargetsDeleteProcessing,
        MatchingTargetsWithProcessingStatus,
    ) as exc:
        raise MatchProcessing from exc

    headers = {
        'Content-Type': 'application/json',
        'Date': date,
        'Connection': 'keep-alive',
        'Server': 'nginx',
    }
    return Response(
        status=HTTPStatus.OK,
        response=response_text,
        headers=headers,
    )
