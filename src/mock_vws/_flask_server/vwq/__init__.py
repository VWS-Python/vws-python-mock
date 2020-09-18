import copy
import email.utils
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import requests
from flask import Flask, Response, request
from werkzeug.datastructures import Headers
from werkzeug.wsgi import ClosingIterator

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

from ..vws._databases import get_all_databases

CLOUDRECO_FLASK_APP = Flask(import_name=__name__)
CLOUDRECO_FLASK_APP.config['PROPAGATE_EXCEPTIONS'] = True


@CLOUDRECO_FLASK_APP.before_request
def validate_request() -> None:
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


# We use a custom response type.
# Without this, a content type is added to all responses.
# Some of our responses need to not have a "Content-Type" header.
class MyResponse(Response):
    def __init__(
        self,
        response: Optional[ClosingIterator] = None,
        status: Optional[str] = None,
        headers: Optional[Headers] = None,
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

        if content_type is None and headers and not content_type_from_headers:
            headers_dict = dict(headers)
            headers_dict.pop('Content-Type')
            self.headers = Headers(headers_dict)


CLOUDRECO_FLASK_APP.response_class = MyResponse


@CLOUDRECO_FLASK_APP.errorhandler(requests.exceptions.ConnectionError)
def handle_connection_error(
    e: requests.exceptions.ConnectionError,
) -> Response:
    # TODO: Issue
    # This is incorrect - it raises on the server but should raise on the
    # client
    # Look into how ``requests`` handles it
    raise e


@CLOUDRECO_FLASK_APP.errorhandler(AuthHeaderMissing)
@CLOUDRECO_FLASK_APP.errorhandler(AuthenticationFailure)
@CLOUDRECO_FLASK_APP.errorhandler(AuthenticationFailureGoodFormatting)
@CLOUDRECO_FLASK_APP.errorhandler(BadImage)
@CLOUDRECO_FLASK_APP.errorhandler(BoundaryNotInBody)
@CLOUDRECO_FLASK_APP.errorhandler(DateFormatNotValid)
@CLOUDRECO_FLASK_APP.errorhandler(DateHeaderNotGiven)
@CLOUDRECO_FLASK_APP.errorhandler(ImageNotGiven)
@CLOUDRECO_FLASK_APP.errorhandler(InactiveProject)
@CLOUDRECO_FLASK_APP.errorhandler(InvalidAcceptHeader)
@CLOUDRECO_FLASK_APP.errorhandler(InvalidIncludeTargetData)
@CLOUDRECO_FLASK_APP.errorhandler(InvalidMaxNumResults)
@CLOUDRECO_FLASK_APP.errorhandler(MalformedAuthHeader)
@CLOUDRECO_FLASK_APP.errorhandler(MaxNumResultsOutOfRange)
@CLOUDRECO_FLASK_APP.errorhandler(NoBoundaryFound)
@CLOUDRECO_FLASK_APP.errorhandler(RequestTimeTooSkewed)
@CLOUDRECO_FLASK_APP.errorhandler(UnknownParameters)
@CLOUDRECO_FLASK_APP.errorhandler(UnsupportedMediaType)
@CLOUDRECO_FLASK_APP.errorhandler(ContentLengthHeaderNotInt)
@CLOUDRECO_FLASK_APP.errorhandler(ContentLengthHeaderTooLarge)
@CLOUDRECO_FLASK_APP.errorhandler(QueryOutOfBounds)
# TODO use a base type for these requests
def handle_request_time_too_skewed(
    e: RequestTimeTooSkewed,
) -> Response:
    response = Response()
    response.status_code = e.status_code
    response.set_data(e.response_text)
    response.headers = Headers(e.headers)
    return response


@CLOUDRECO_FLASK_APP.route('/v1/query', methods=['POST'])
def query() -> Response:

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
    ):
        # We return an example 500 response.
        # Each response given by Vuforia is different.
        #
        # Sometimes Vuforia will ignore matching targets with the
        # processing status, but we choose to:
        # * Do the most unexpected thing.
        # * Be consistent with every response.
        resources_dir = Path(__file__).parent.parent.parent / 'resources'
        filename = 'match_processing_response.html'
        match_processing_resp_file = resources_dir / filename
        content_type = 'text/html; charset=ISO-8859-1'
        headers = {
            'Content-Type': 'text/html; charset=ISO-8859-1',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'Cache-Control': 'must-revalidate,no-cache,no-store',
        }
        response_text = match_processing_resp_file.read_text()
        return Response(
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
            response=response_text,
            headers=headers,
        )

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
