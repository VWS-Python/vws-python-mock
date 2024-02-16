"""
A fake implementation of the Vuforia Web Query API using Flask.

See
https://library.vuforia.com/web-api/vuforia-query-web-api
"""

import email.utils
from enum import StrEnum, auto
from http import HTTPStatus

import requests
from flask import Flask, Response, request
from pydantic_settings import BaseSettings

from mock_vws._query_tools import (
    get_query_match_response_text,
)
from mock_vws._query_validators import run_query_validators
from mock_vws._query_validators.exceptions import (
    ValidatorException,
)
from mock_vws.database import VuforiaDatabase
from mock_vws.image_matchers import (
    ExactMatcher,
    ImageMatcher,
    StructuralSimilarityMatcher,
)

CLOUDRECO_FLASK_APP = Flask(import_name=__name__)
CLOUDRECO_FLASK_APP.config["PROPAGATE_EXCEPTIONS"] = True


class _ImageMatcherChoice(StrEnum):
    """Image matcher choices."""

    EXACT = auto()
    STRUCTURAL_SIMILARITY = auto()

    def to_image_matcher(self) -> ImageMatcher:
        """Get the image matcher."""
        ssim_matcher = StructuralSimilarityMatcher()
        matcher = {
            _ImageMatcherChoice.EXACT: ExactMatcher(),
            _ImageMatcherChoice.STRUCTURAL_SIMILARITY: ssim_matcher,
        }[self]
        assert isinstance(matcher, ImageMatcher)
        return matcher


class VWQSettings(BaseSettings):
    """Settings for the VWQ Flask app."""

    vwq_host: str = ""
    target_manager_base_url: str
    query_image_matcher: _ImageMatcherChoice = (
        _ImageMatcherChoice.STRUCTURAL_SIMILARITY
    )


def get_all_databases() -> set[VuforiaDatabase]:
    """
    Get all database objects from the target manager back-end.
    """
    settings = VWQSettings.model_validate(obj={})
    response = requests.get(
        url=f"{settings.target_manager_base_url}/databases",
        timeout=30,
    )
    return {
        VuforiaDatabase.from_dict(database_dict=database_dict)
        for database_dict in response.json()
    }


@CLOUDRECO_FLASK_APP.before_request
def set_terminate_wsgi_input() -> None:
    """
    We set ``wsgi.input_terminated`` to ``True`` when going through
    ``requests`` in our tests, so that requests have the given
    ``Content-Length`` headers and the given data in ``request.headers`` and
    ``request.data``.

    We do not set this at all when running an application as standalone.
    This is because when running the Flask application, if this is set,
    reading ``request.data`` hangs.

    Therefore, when running the real Flask application, the behavior is not the
    same as the real Vuforia.
    This is documented as a difference in the documentation for this package.
    """
    try:
        set_terminate_wsgi_input_true = (
            CLOUDRECO_FLASK_APP.config["VWS_MOCK_TERMINATE_WSGI_INPUT"] is True
        )
    except KeyError:
        set_terminate_wsgi_input_true = False

    if set_terminate_wsgi_input_true:
        request.environ["wsgi.input_terminated"] = True


@CLOUDRECO_FLASK_APP.errorhandler(ValidatorException)
def handle_exceptions(exc: ValidatorException) -> Response:
    """
    Return the error response associated with the given exception.
    """
    response = Response(
        status=exc.status_code.value,
        response=exc.response_text,
        headers=exc.headers,
    )

    response.headers.clear()
    response.headers.extend(exc.headers)
    return response


@CLOUDRECO_FLASK_APP.route("/v1/query", methods=["POST"])
def query() -> Response:
    """
    Perform an image recognition query.
    """
    settings = VWQSettings.model_validate(obj={})
    query_match_checker = settings.query_image_matcher.to_image_matcher()

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

    response_text = get_query_match_response_text(
        request_headers=dict(request.headers),
        request_body=request_body,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
        query_match_checker=query_match_checker,
    )

    headers = {
        "Content-Type": "application/json",
        "Date": date,
        "Connection": "keep-alive",
        "Server": "nginx",
    }
    return Response(
        status=HTTPStatus.OK,
        response=response_text,
        headers=headers,
    )


if __name__ == "__main__":  # pragma: no cover
    SETTINGS = VWQSettings.model_validate(obj={})
    CLOUDRECO_FLASK_APP.run(host=SETTINGS.vwq_host)
