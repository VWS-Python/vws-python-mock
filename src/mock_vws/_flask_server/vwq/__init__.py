import base64
import cgi
import datetime
import email.utils
import io
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytz
from flask import Flask, Response, make_response, request
from requests import codes
import requests
from mock_vws._query_tools import (
    ActiveMatchingTargetsDeleteProcessing,
    MatchingTargetsWithProcessingStatus,
    get_query_match_response_text,
)

from mock_vws._base64_decoding import decode_base64
from mock_vws._constants import ResultCodes, TargetStatuses
from mock_vws._database_matchers import get_database_matching_client_keys
from mock_vws._mock_common import json_dump, parse_multipart
from mock_vws.database import VuforiaDatabase

from ..vws._databases import get_all_databases
from mock_vws._query_validators import run_query_validators
from mock_vws._query_validators.exceptions import (
    DateHeaderNotGiven,
    DateFormatNotValid,
    RequestTimeTooSkewed,
    BadImage,
    AuthenticationFailure,
    AuthenticationFailureGoodFormatting,
    ImageNotGiven,
    AuthHeaderMissing,
    MalformedAuthHeader,
    UnknownParameters,
    InactiveProject,
    InvalidMaxNumResults,
    MaxNumResultsOutOfRange,
    InvalidIncludeTargetData,
    UnsupportedMediaType,
    InvalidAcceptHeader,
    BoundaryNotInBody,
    NoBoundaryFound,
    QueryOutOfBounds,
    ContentLengthHeaderTooLarge,
    ContentLengthHeaderNotInt
)

CLOUDRECO_FLASK_APP = Flask(__name__)
CLOUDRECO_FLASK_APP.config['PROPAGATE_EXCEPTIONS'] = True


@CLOUDRECO_FLASK_APP.before_request
def validate_request() -> None:
    databases = get_all_databases()
    run_query_validators(
        request_headers=dict(request.headers),
        request_body=request.input_stream.getvalue(),
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )



class MyResponse(Response):
    default_mimetype = None

CLOUDRECO_FLASK_APP.response_class = MyResponse

@CLOUDRECO_FLASK_APP.errorhandler(ContentLengthHeaderTooLarge)
def handle_content_length_header_too_large(
    e: ContentLengthHeaderTooLarge,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    response.headers = {'Connection': 'keep-alive'}
    assert isinstance(response, Response)
    return response

@CLOUDRECO_FLASK_APP.errorhandler(requests.exceptions.ConnectionError)
def handle_connection_error(
    e: requests.exceptions.ConnectionError,
) -> Response:
    raise e
    response = make_response(e.response_text, e.status_code)
    response.headers = {'Connection': 'keep-alive'}
    assert isinstance(response, Response)
    return response

@CLOUDRECO_FLASK_APP.errorhandler(UnsupportedMediaType)
def handle_unsupported_media_type(
    e: UnsupportedMediaType,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    assert isinstance(response, Response)
    return response

@CLOUDRECO_FLASK_APP.errorhandler(InvalidAcceptHeader)
def handle_invalid_accept_header(
    e: InvalidAcceptHeader,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    assert isinstance(response, Response)
    return response

@CLOUDRECO_FLASK_APP.errorhandler(BadImage)
def handle_bad_image(
    e: BadImage,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    assert isinstance(response, Response)
    return response

@CLOUDRECO_FLASK_APP.errorhandler(UnknownParameters)
def handle_unknown_parameters(
    e: UnknownParameters,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    assert isinstance(response, Response)
    return response


@CLOUDRECO_FLASK_APP.errorhandler(RequestTimeTooSkewed)
def handle_request_time_too_skewed(
    e: RequestTimeTooSkewed,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    assert isinstance(response, Response)
    return response


@CLOUDRECO_FLASK_APP.errorhandler(ImageNotGiven)
def handle_image_not_given(
    e: ImageNotGiven,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    assert isinstance(response, Response)
    return response


@CLOUDRECO_FLASK_APP.errorhandler(InactiveProject)
def handle_inactive_project(
    e: InactiveProject,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    assert isinstance(response, Response)
    return response


@CLOUDRECO_FLASK_APP.errorhandler(InvalidIncludeTargetData)
def handle_invalid_include_target_data(
    e: InvalidIncludeTargetData,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    assert isinstance(response, Response)
    return response

@CLOUDRECO_FLASK_APP.errorhandler(InvalidMaxNumResults)
def handle_invalid_max_num_results(
    e: InvalidMaxNumResults,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    assert isinstance(response, Response)
    return response

@CLOUDRECO_FLASK_APP.errorhandler(MaxNumResultsOutOfRange)
def handle_max_num_results_out_of_range(
    e: MaxNumResultsOutOfRange,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    assert isinstance(response, Response)
    return response


@CLOUDRECO_FLASK_APP.errorhandler(NoBoundaryFound)
def handle_no_boundary_found(
    e: NoBoundaryFound,
) -> Response:
    content_type = 'text/html;charset=UTF-8'
    response = make_response(e.response_text, e.status_code)
    response.headers['Content-Type'] = content_type
    assert isinstance(response, Response)
    return response

@CLOUDRECO_FLASK_APP.errorhandler(BoundaryNotInBody)
def handle_boundary_not_in_body(
    e: BoundaryNotInBody,
) -> Response:
    content_type = 'text/html;charset=UTF-8'
    response = make_response(e.response_text, e.status_code)
    response.headers['Content-Type'] = content_type
    assert isinstance(response, Response)
    return response


@CLOUDRECO_FLASK_APP.errorhandler(AuthenticationFailure)
def handle_authentication_failure(
    e: AuthenticationFailure,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    response.headers['WWW-Authenticate'] = 'VWS'
    assert isinstance(response, Response)
    return response

@CLOUDRECO_FLASK_APP.errorhandler(AuthenticationFailureGoodFormatting)
def handle_authentication_failure_good_formatting(
    e: AuthenticationFailureGoodFormatting,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    response.headers['WWW-Authenticate'] = 'VWS'
    assert isinstance(response, Response)
    return response

@CLOUDRECO_FLASK_APP.errorhandler(QueryOutOfBounds)
def handle_query_out_of_bounds(
    e: QueryOutOfBounds,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    content_type = 'text/html; charset=ISO-8859-1'
    response.headers['Content-Type'] = content_type
    cache_control = 'must-revalidate,no-cache,no-store'
    response.headers['Cache-Control'] = cache_control
    assert isinstance(response, Response)
    return response

@CLOUDRECO_FLASK_APP.errorhandler(AuthHeaderMissing)
def handle_auth_header_missing(
    e: AuthHeaderMissing,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    content_type = 'text/plain; charset=ISO-8859-1'
    response.headers['Content-Type'] = content_type
    response.headers['WWW-Authenticate'] = 'VWS'
    assert isinstance(response, Response)
    return response

@CLOUDRECO_FLASK_APP.errorhandler(DateFormatNotValid)
def handle_date_format_not_valid(
    e: DateFormatNotValid,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    content_type = 'text/plain; charset=ISO-8859-1'
    response.headers['Content-Type'] = content_type
    response.headers['WWW-Authenticate'] = 'VWS'
    assert isinstance(response, Response)
    return response

@CLOUDRECO_FLASK_APP.errorhandler(MalformedAuthHeader)
def handle_malformed_auth_header(
    e: MalformedAuthHeader,
) -> Response:
    response = make_response(e.response_text, e.status_code)
    content_type = 'text/plain; charset=ISO-8859-1'
    response.headers['Content-Type'] = content_type
    response.headers['WWW-Authenticate'] = 'VWS'
    assert isinstance(response, Response)
    return response


@CLOUDRECO_FLASK_APP.after_request
def set_headers(response: Response) -> Response:
    # raise requests.exceptions.ConnectionError
    response.headers['Connection'] = 'keep-alive'
    response.headers['Server'] = 'nginx'
    content_length = len(response.data)
    response.headers['Content-Length'] = str(content_length)
    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    response.headers['Date'] = date
    if response.status_code in (
        codes.OK,
        codes.UNPROCESSABLE_ENTITY,
        codes.BAD_REQUEST,
        codes.FORBIDDEN,
        codes.UNAUTHORIZED,
    ) and 'Content-Type' not in response.headers:
        response.headers['Content-Type'] = 'application/json'
    return response


@CLOUDRECO_FLASK_APP.route('/v1/query', methods=['POST'])
def query() -> Tuple[str, int]:


    # TODO these should be configurable
    query_processes_deletion_seconds = 0.2
    query_recognizes_deletion_seconds = 0.2
    databases = get_all_databases()

    try:
        response_text = get_query_match_response_text(
            request_headers=dict(request.headers),
            request_body=request.input_stream.getvalue(),
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
        cache_control = 'must-revalidate,no-cache,no-store'
        # TODO remove legacy
        # context.headers['Cache-Control'] = cache_control
        content_type = 'text/html; charset=ISO-8859-1'
        # TODO remove legacy
        # context.headers['Content-Type'] = content_type
        # TODO remove file copied to this dir
        return (
            Path(match_processing_resp_file).read_text(),
            codes.INTERNAL_SERVER_ERROR,
            {
                'Cache-Control': cache_control,
                'Content-Type': content_type,
            },
        )

    return response_text
