"""
A fake implementation of the Vuforia Web Query API using Flask.

See
https://library.vuforia.com/articles/Solution/How-To-Perform-an-Image-Recognition-Query
"""

import email.utils
from http import HTTPStatus
from typing import Final, Set

import requests
from flask import Flask, Response, request

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

CLOUDRECO_FLASK_APP = Flask(import_name=__name__)
CLOUDRECO_FLASK_APP.config['PROPAGATE_EXCEPTIONS'] = True
STORAGE_BASE_URL: Final[str] = 'http://vws-mock-storage:5000'


def get_all_databases() -> Set[VuforiaDatabase]:
    """
    Get all database objects from the storage back-end.
    """
    response = requests.get(url=STORAGE_BASE_URL + '/databases')
    return set(
        VuforiaDatabase.from_dict(database_dict=database_dict)
        for database_dict in response.json()
    )


@CLOUDRECO_FLASK_APP.before_request
def set_terminate_wsgi_input() -> None:
    """
    We set ``wsgi.input_terminated`` to ``True`` when going through
    ``requests``, so that requests have the given ``Content-Length`` headers
    and the given data in ``request.headers`` and ``request.data``.

    We set this to ``False`` when running an application as standalone.
    This is because when running the Flask application, if this is set,
    reading ``request.data`` hangs.

    Therefore, when running the real Flask application, the behavior is not the
    same as the real Vuforia.
    This is documented as a difference in the documentation for this package.
    """
    terminate_wsgi_input = CLOUDRECO_FLASK_APP.config.get(
        'TERMINATE_WSGI_INPUT',
        False,
    )
    request.environ['wsgi.input_terminated'] = terminate_wsgi_input


class ResponseNoContentTypeAdded(Response):
    """
    A custom response type.

    Without this, a content type is added to all responses.
    Some of our responses need to not have a "Content-Type" header.
    """

    # When https://github.com/python/typeshed/pull/4563 is shipped in a future
    # release of mypy, we can remove this ignore.
    default_mimetype = None  # type: ignore


CLOUDRECO_FLASK_APP.response_class = ResponseNoContentTypeAdded


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
    query_processes_deletion_seconds = 0.2
    query_recognizes_deletion_seconds = 0.2

    databases = get_all_databases()
    request_body = request.stream.read()
    run_query_validators(
        request_headers=dict(request.headers),
        request_body=request_body,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )
    date = email.utils.formatdate(None, localtime=False, usegmt=True)

    try:
        response_text = get_query_match_response_text(
            request_headers=dict(request.headers),
            request_body=request_body,
            request_method=request.method,
            request_path=request.path,
            databases=databases,
            query_processes_deletion_seconds=query_processes_deletion_seconds,
            query_recognizes_deletion_seconds=(
                query_recognizes_deletion_seconds
            ),
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


if __name__ == '__main__':  # pragma: no cover
    CLOUDRECO_FLASK_APP.run(debug=True, host='0.0.0.0')
