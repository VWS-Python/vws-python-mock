"""
A fake implementation of the Vuforia Web Services API.

See
https://library.vuforia.com/web-api/cloud-targets-web-services-api
"""

import base64
import email.utils
import json
import logging
import uuid
from enum import StrEnum, auto
from http import HTTPStatus

import requests
from flask import Flask, Response, request
from pydantic_settings import BaseSettings

from mock_vws._constants import ResultCodes, TargetStatuses
from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._mock_common import json_dump
from mock_vws._services_validators import run_services_validators
from mock_vws._services_validators.exceptions import (
    Fail,
    TargetStatusNotSuccess,
    TargetStatusProcessing,
    ValidatorException,
)
from mock_vws.database import VuforiaDatabase
from mock_vws.image_matchers import (
    ExactMatcher,
    ImageMatcher,
    StructuralSimilarityMatcher,
)
from mock_vws.target import Target
from mock_vws.target_raters import (
    HardcodedTargetTrackingRater,
)

VWS_FLASK_APP = Flask(import_name=__name__)
VWS_FLASK_APP.config["PROPAGATE_EXCEPTIONS"] = True


_LOGGER = logging.getLogger(__name__)


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


class VWSSettings(BaseSettings):
    """Settings for the VWS Flask app."""

    target_manager_base_url: str
    processing_time_seconds: float = 2
    vws_host: str = ""
    duplicates_image_matcher: (
        _ImageMatcherChoice
    ) = _ImageMatcherChoice.STRUCTURAL_SIMILARITY


def get_all_databases() -> set[VuforiaDatabase]:
    """
    Get all database objects from the task manager back-end.
    """
    settings = VWSSettings.model_validate(obj={})
    timeout_seconds = 30
    response = requests.get(
        url=f"{settings.target_manager_base_url}/databases",
        timeout=timeout_seconds,
    )
    return {
        VuforiaDatabase.from_dict(database_dict=database_dict)
        for database_dict in response.json()
    }


@VWS_FLASK_APP.before_request
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
            VWS_FLASK_APP.config["VWS_MOCK_TERMINATE_WSGI_INPUT"] is True
        )
    except KeyError:
        set_terminate_wsgi_input_true = False

    if set_terminate_wsgi_input_true:
        request.environ["wsgi.input_terminated"] = True


@VWS_FLASK_APP.before_request
def validate_request() -> None:
    """
    Run validators on the request.
    """
    databases = get_all_databases()
    run_services_validators(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )


@VWS_FLASK_APP.errorhandler(ValidatorException)
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


@VWS_FLASK_APP.route("/targets", methods=["POST"])
def add_target() -> Response:
    """
    Add a target.

    Fake implementation of
    https://library.vuforia.com/web-api/cloud-targets-web-services-api#add
    """
    settings = VWSSettings.model_validate(obj={})
    databases = get_all_databases()
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )

    # We do not use ``request.get_json(force=True)`` because this only works
    # when the content type is given as ``application/json``.
    request_json = json.loads(request.data)
    name = request_json["name"]
    active_flag = request_json.get("active_flag")
    if active_flag is None:
        active_flag = True

    # This rater is not used.
    target_tracking_rater = HardcodedTargetTrackingRater(rating=1)

    new_target = Target(
        name=name,
        width=request_json["width"],
        image_value=base64.b64decode(request_json["image"]),
        active_flag=active_flag,
        processing_time_seconds=settings.processing_time_seconds,
        application_metadata=request_json.get("application_metadata"),
        target_tracking_rater=target_tracking_rater,
    )

    databases_url = f"{settings.target_manager_base_url}/databases"
    timeout_seconds = 30
    requests.post(
        url=f"{databases_url}/{database.database_name}/targets",
        json=new_target.to_dict(),
        timeout=timeout_seconds,
    )

    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    headers = {
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "server": "envoy",
        "Date": date,
        "x-envoy-upstream-service-time": "5",
        "strict-transport-security": "max-age=31536000",
        "x-aws-region": "us-east-2, us-west-2",
        "x-content-type-options": "nosniff",
    }

    body = {
        "transaction_id": uuid.uuid4().hex,
        "result_code": ResultCodes.TARGET_CREATED.value,
        "target_id": new_target.target_id,
    }

    return Response(
        status=HTTPStatus.CREATED,
        response=json_dump(body),
        headers=headers,
    )


@VWS_FLASK_APP.route("/targets/<string:target_id>", methods=["GET"])
def get_target(target_id: str) -> Response:
    """
    Get details of a target.

    Fake implementation of
    https://library.vuforia.com/web-api/cloud-targets-web-services-api#target-record
    """
    databases = get_all_databases()
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )

    (target,) = (
        target for target in database.targets if target.target_id == target_id
    )

    target_record = {
        "target_id": target.target_id,
        "active_flag": target.active_flag,
        "name": target.name,
        "width": target.width,
        "tracking_rating": target.tracking_rating,
        "reco_rating": target.reco_rating,
    }

    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    headers = {
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "server": "envoy",
        "Date": date,
        "x-envoy-upstream-service-time": "5",
        "strict-transport-security": "max-age=31536000",
        "x-aws-region": "us-east-2, us-west-2",
        "x-content-type-options": "nosniff",
    }
    body = {
        "result_code": ResultCodes.SUCCESS.value,
        "transaction_id": uuid.uuid4().hex,
        "target_record": target_record,
        "status": target.status,
    }
    return Response(
        status=HTTPStatus.OK,
        response=json_dump(body),
        headers=headers,
    )


@VWS_FLASK_APP.route("/targets/<string:target_id>", methods=["DELETE"])
def delete_target(target_id: str) -> Response:
    """
    Delete a target.

    Fake implementation of
    https://library.vuforia.com/web-api/cloud-targets-web-services-api#delete
    """
    settings = VWSSettings.model_validate(obj={})
    databases = get_all_databases()
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )

    (target,) = (
        target for target in database.targets if target.target_id == target_id
    )

    if target.status == TargetStatuses.PROCESSING.value:
        raise TargetStatusProcessing

    databases_url = f"{settings.target_manager_base_url}/databases"
    requests.delete(
        url=f"{databases_url}/{database.database_name}/targets/{target_id}",
        timeout=30,
    )

    body = {
        "transaction_id": uuid.uuid4().hex,
        "result_code": ResultCodes.SUCCESS.value,
    }
    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    headers = {
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "server": "envoy",
        "Date": date,
        "x-envoy-upstream-service-time": "5",
        "strict-transport-security": "max-age=31536000",
        "x-aws-region": "us-east-2, us-west-2",
        "x-content-type-options": "nosniff",
    }
    return Response(
        status=HTTPStatus.OK,
        response=json_dump(body),
        headers=headers,
    )


@VWS_FLASK_APP.route("/summary", methods=["GET"])
def database_summary() -> Response:
    """
    Get a database summary report.

    Fake implementation of
    https://library.vuforia.com/web-api/cloud-targets-web-services-api#summary-report
    """
    databases = get_all_databases()
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )

    body = {
        "result_code": ResultCodes.SUCCESS.value,
        "transaction_id": uuid.uuid4().hex,
        "name": database.database_name,
        "active_images": len(database.active_targets),
        "inactive_images": len(database.inactive_targets),
        "failed_images": len(database.failed_targets),
        "target_quota": database.target_quota,
        "total_recos": database.total_recos,
        "current_month_recos": database.current_month_recos,
        "previous_month_recos": database.previous_month_recos,
        "processing_images": len(database.processing_targets),
        "reco_threshold": database.reco_threshold,
        "request_quota": database.request_quota,
        # We have ``self.request_count`` but Vuforia always shows 0.
        # This was not always the case.
        "request_usage": 0,
    }
    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    headers = {
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "server": "envoy",
        "Date": date,
        "x-envoy-upstream-service-time": "5",
        "strict-transport-security": "max-age=31536000",
        "x-aws-region": "us-east-2, us-west-2",
        "x-content-type-options": "nosniff",
    }
    return Response(
        status=HTTPStatus.OK,
        response=json_dump(body),
        headers=headers,
    )


@VWS_FLASK_APP.route("/summary/<string:target_id>", methods=["GET"])
def target_summary(target_id: str) -> Response:
    """
    Get a summary report for a target.

    Fake implementation of
    https://library.vuforia.com/web-api/cloud-targets-web-services-api#retrieve-report
    """
    databases = get_all_databases()
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )

    (target,) = (
        target for target in database.targets if target.target_id == target_id
    )
    body = {
        "status": target.status,
        "transaction_id": uuid.uuid4().hex,
        "result_code": ResultCodes.SUCCESS.value,
        "database_name": database.database_name,
        "target_name": target.name,
        "upload_date": target.upload_date.strftime("%Y-%m-%d"),
        "active_flag": target.active_flag,
        "tracking_rating": target.tracking_rating,
        "total_recos": target.total_recos,
        "current_month_recos": target.current_month_recos,
        "previous_month_recos": target.previous_month_recos,
    }
    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    headers = {
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "server": "envoy",
        "Date": date,
        "x-envoy-upstream-service-time": "5",
        "strict-transport-security": "max-age=31536000",
        "x-aws-region": "us-east-2, us-west-2",
        "x-content-type-options": "nosniff",
    }
    return Response(
        status=HTTPStatus.OK,
        response=json_dump(body),
        headers=headers,
    )


@VWS_FLASK_APP.route("/duplicates/<string:target_id>", methods=["GET"])
def get_duplicates(target_id: str) -> Response:
    """
    Get targets which may be considered duplicates of a given target.

    Fake implementation of
    https://library.vuforia.com/web-api/cloud-targets-web-services-api#check
    """
    databases = get_all_databases()
    settings = VWSSettings.model_validate(obj={})
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )
    image_match_checker = settings.duplicates_image_matcher.to_image_matcher()

    (target,) = (
        target for target in database.targets if target.target_id == target_id
    )
    other_targets = database.targets - {target}

    similar_targets: list[str] = [
        other.target_id
        for other in other_targets
        if image_match_checker(
            first_image_content=target.image_value,
            second_image_content=other.image_value,
        )
        and TargetStatuses.FAILED.value not in {target.status, other.status}
        and TargetStatuses.PROCESSING.value != other.status
        and other.active_flag
    ]

    body = {
        "transaction_id": uuid.uuid4().hex,
        "result_code": ResultCodes.SUCCESS.value,
        "similar_targets": similar_targets,
    }

    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    headers = {
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "server": "envoy",
        "Date": date,
        "x-envoy-upstream-service-time": "5",
        "strict-transport-security": "max-age=31536000",
        "x-aws-region": "us-east-2, us-west-2",
        "x-content-type-options": "nosniff",
    }
    return Response(
        status=HTTPStatus.OK,
        response=json_dump(body),
        headers=headers,
    )


@VWS_FLASK_APP.route("/targets", methods=["GET"])
def target_list() -> Response:
    """
    Get a list of all targets.

    Fake implementation of
    https://library.vuforia.com/web-api/cloud-targets-web-services-api#details-list
    """
    databases = get_all_databases()
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )
    results = [target.target_id for target in database.not_deleted_targets]

    body = {
        "transaction_id": uuid.uuid4().hex,
        "result_code": ResultCodes.SUCCESS.value,
        "results": results,
    }
    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    headers = {
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "server": "envoy",
        "Date": date,
        "x-envoy-upstream-service-time": "5",
        "strict-transport-security": "max-age=31536000",
        "x-aws-region": "us-east-2, us-west-2",
        "x-content-type-options": "nosniff",
    }
    return Response(
        status=HTTPStatus.OK,
        response=json_dump(body),
        headers=headers,
    )


@VWS_FLASK_APP.route("/targets/<string:target_id>", methods=["PUT"])
def update_target(target_id: str) -> Response:
    """
    Update a target.

    Fake implementation of
    https://library.vuforia.com/web-api/cloud-targets-web-services-api#update
    """
    settings = VWSSettings.model_validate(obj={})
    # We do not use ``request.get_json(force=True)`` because this only works
    # when the content type is given as ``application/json``.
    request_json = json.loads(request.data)
    databases = get_all_databases()
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )

    (target,) = (
        target for target in database.targets if target.target_id == target_id
    )

    if target.status != TargetStatuses.SUCCESS.value:
        raise TargetStatusNotSuccess

    update_values: dict[str, str | int | float | bool | None] = {}
    if "width" in request_json:
        update_values["width"] = request_json["width"]

    if "active_flag" in request_json:
        active_flag = request_json["active_flag"]
        if active_flag is None:
            _LOGGER.warning(
                msg=(
                    'The value of "active_flag" was None. '
                    "This is not allowed. "
                ),
            )
            raise Fail(status_code=HTTPStatus.BAD_REQUEST)
        update_values["active_flag"] = active_flag

    if "application_metadata" in request_json:
        application_metadata = request_json["application_metadata"]
        if application_metadata is None:
            _LOGGER.warning(
                msg=(
                    'The value of "application_metadata" was None. '
                    "This is not allowed."
                ),
            )
            raise Fail(status_code=HTTPStatus.BAD_REQUEST)
        update_values["application_metadata"] = application_metadata

    if "name" in request_json:
        name = request_json["name"]
        update_values["name"] = name

    if "image" in request_json:
        image = request_json["image"]
        update_values["image"] = image

    put_url = (
        f"{settings.target_manager_base_url}/databases/"
        f"{database.database_name}/targets/{target_id}"
    )
    requests.put(url=put_url, json=update_values, timeout=30)

    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    headers = {
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "server": "envoy",
        "Date": date,
        "x-envoy-upstream-service-time": "5",
        "strict-transport-security": "max-age=31536000",
        "x-aws-region": "us-east-2, us-west-2",
        "x-content-type-options": "nosniff",
    }
    body = {
        "result_code": ResultCodes.SUCCESS.value,
        "transaction_id": uuid.uuid4().hex,
    }
    return Response(
        status=HTTPStatus.OK,
        response=json_dump(body),
        headers=headers,
    )


if __name__ == "__main__":  # pragma: no cover
    SETTINGS = VWSSettings.model_validate(obj={})
    VWS_FLASK_APP.run(host=SETTINGS.vws_host)
