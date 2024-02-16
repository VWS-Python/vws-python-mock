"""
A fake implementation of the Vuforia Web Services API.

See
https://library.vuforia.com/web-api/cloud-targets-web-services-api
"""

from __future__ import annotations

import base64
import dataclasses
import datetime
import email.utils
import uuid
from http import HTTPStatus
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from requests_mock import DELETE, GET, POST, PUT

from mock_vws._constants import ResultCodes, TargetStatuses
from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._mock_common import Route, json_dump
from mock_vws._services_validators import run_services_validators
from mock_vws._services_validators.exceptions import (
    Fail,
    TargetStatusNotSuccess,
    TargetStatusProcessing,
    ValidatorException,
)
from mock_vws.target import Target

if TYPE_CHECKING:
    from collections.abc import Callable

    from requests_mock.request import Request
    from requests_mock.response import Context

    from mock_vws.image_matchers import ImageMatcher
    from mock_vws.target_manager import TargetManager
    from mock_vws.target_raters import TargetTrackingRater

_TARGET_ID_PATTERN = "[A-Za-z0-9]+"


_ROUTES: set[Route] = set()


def route(
    path_pattern: str,
    http_methods: set[str],
) -> Callable[[Callable[..., str]], Callable[..., str]]:
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
        _ROUTES.add(
            Route(
                route_name=method.__name__,
                path_pattern=path_pattern,
                http_methods=frozenset(http_methods),
            ),
        )

        return method

    return decorator


class MockVuforiaWebServicesAPI:
    """
    A fake implementation of the Vuforia Web Services API.

    This implementation is tied to the implementation of `requests_mock`.
    """

    def __init__(
        self,
        target_manager: TargetManager,
        processing_time_seconds: float,
        duplicate_match_checker: ImageMatcher,
        target_tracking_rater: TargetTrackingRater,
    ) -> None:
        """
        Args:
            target_manager: Target Manager which stores databases.
            processing_time_seconds: The number of seconds to process each
              image for. In the real Vuforia Web Services, this is not
              deterministic.
            duplicate_match_checker: A callable which takes two image values
              and returns whether they are duplicates.
            target_tracking_rater: A callable for rating targets for tracking.

        Attributes:
            routes: The `Route`s to be used in the mock.
        """
        self._target_manager = target_manager
        self.routes: set[Route] = _ROUTES
        self._processing_time_seconds = processing_time_seconds
        self._duplicate_match_checker = duplicate_match_checker
        self._target_tracking_rater = target_tracking_rater

    @route(
        path_pattern="/targets",
        http_methods={POST},
    )
    def add_target(self, request: Request, context: Context) -> str:
        """
        Add a target.

        Fake implementation of
        https://library.vuforia.com/web-api/cloud-targets-web-services-api#add
        """
        try:
            run_services_validators(
                request_headers=request.headers,
                request_body=request.body,
                request_method=request.method,
                request_path=request.path,
                databases=self._target_manager.databases,
            )
        except ValidatorException as exc:
            context.headers = exc.headers
            context.status_code = exc.status_code
            return exc.response_text

        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self._target_manager.databases,
        )

        given_active_flag = request.json().get("active_flag")
        active_flag = {
            None: True,
            True: True,
            False: False,
        }[given_active_flag]

        application_metadata = request.json().get("application_metadata")

        new_target = Target(
            name=request.json()["name"],
            width=request.json()["width"],
            image_value=base64.b64decode(request.json()["image"]),
            active_flag=active_flag,
            processing_time_seconds=self._processing_time_seconds,
            application_metadata=application_metadata,
            target_tracking_rater=self._target_tracking_rater,
        )
        database.targets.add(new_target)

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        context.status_code = HTTPStatus.CREATED
        body = {
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.TARGET_CREATED.value,
            "target_id": new_target.target_id,
        }
        body_json = json_dump(body)
        context.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "Content-Length": str(len(body_json)),
            "x-envoy-upstream-service-time": "5",
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }
        return body_json

    @route(
        path_pattern=f"/targets/{_TARGET_ID_PATTERN}",
        http_methods={DELETE},
    )
    def delete_target(self, request: Request, context: Context) -> str:
        """
        Delete a target.

        Fake implementation of
        https://library.vuforia.com/web-api/cloud-targets-web-services-api#delete
        """
        try:
            run_services_validators(
                request_headers=request.headers,
                request_body=request.body,
                request_method=request.method,
                request_path=request.path,
                databases=self._target_manager.databases,
            )
        except ValidatorException as exc:
            context.headers = exc.headers
            context.status_code = exc.status_code
            return exc.response_text

        body: dict[str, str] = {}
        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self._target_manager.databases,
        )

        target_id = request.path.split("/")[-1]
        target = database.get_target(target_id=target_id)

        if target.status == TargetStatuses.PROCESSING.value:
            target_processing_exception = TargetStatusProcessing()
            context.headers = target_processing_exception.headers
            context.status_code = target_processing_exception.status_code
            return target_processing_exception.response_text

        now = datetime.datetime.now(tz=target.upload_date.tzinfo)
        new_target = dataclasses.replace(target, delete_date=now)
        database.targets.remove(target)
        database.targets.add(new_target)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)

        body = {
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.SUCCESS.value,
        }
        body_json = json_dump(body)
        context.headers = {
            "Connection": "keep-alive",
            "Content-Length": str(len(body_json)),
            "Content-Type": "application/json",
            "Date": date,
            "server": "envoy",
            "x-envoy-upstream-service-time": "5",
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }
        return body_json

    @route(path_pattern="/summary", http_methods={GET})
    def database_summary(self, request: Request, context: Context) -> str:
        """
        Get a database summary report.

        Fake implementation of
        https://library.vuforia.com/web-api/cloud-targets-web-services-api#summary-report
        """
        try:
            run_services_validators(
                request_headers=request.headers,
                request_body=request.body,
                request_method=request.method,
                request_path=request.path,
                databases=self._target_manager.databases,
            )
        except ValidatorException as exc:
            context.headers = exc.headers
            context.status_code = exc.status_code
            return exc.response_text

        body: dict[str, str | int] = {}

        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self._target_manager.databases,
        )

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
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
            "request_usage": 0,
        }
        body_json = json_dump(body)
        context.headers = {
            "Connection": "keep-alive",
            "Content-Length": str(len(body_json)),
            "Content-Type": "application/json",
            "Date": date,
            "server": "envoy",
            "x-envoy-upstream-service-time": "5",
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }
        return body_json

    @route(path_pattern="/targets", http_methods={GET})
    def target_list(self, request: Request, context: Context) -> str:
        """
        Get a list of all targets.

        Fake implementation of
        https://library.vuforia.com/web-api/cloud-targets-web-services-api#details-list
        """
        try:
            run_services_validators(
                request_headers=request.headers,
                request_body=request.body,
                request_method=request.method,
                request_path=request.path,
                databases=self._target_manager.databases,
            )
        except ValidatorException as exc:
            context.headers = exc.headers
            context.status_code = exc.status_code
            return exc.response_text

        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self._target_manager.databases,
        )

        date = email.utils.formatdate(None, localtime=False, usegmt=True)

        response_results = [
            target.target_id for target in database.not_deleted_targets
        ]
        body: dict[str, str | list[str]] = {
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.SUCCESS.value,
            "results": response_results,
        }
        body_json = json_dump(body)
        context.headers = {
            "Connection": "keep-alive",
            "Content-Length": str(len(body_json)),
            "Content-Type": "application/json",
            "Date": date,
            "server": "envoy",
            "x-envoy-upstream-service-time": "5",
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }
        return body_json

    @route(path_pattern=f"/targets/{_TARGET_ID_PATTERN}", http_methods={GET})
    def get_target(self, request: Request, context: Context) -> str:
        """
        Get details of a target.

        Fake implementation of
        https://library.vuforia.com/web-api/cloud-targets-web-services-api#target-record
        """
        try:
            run_services_validators(
                request_headers=request.headers,
                request_body=request.body,
                request_method=request.method,
                request_path=request.path,
                databases=self._target_manager.databases,
            )
        except ValidatorException as exc:
            context.headers = exc.headers
            context.status_code = exc.status_code
            return exc.response_text

        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self._target_manager.databases,
        )
        target_id = request.path.split("/")[-1]
        target = database.get_target(target_id=target_id)

        target_record = {
            "target_id": target.target_id,
            "active_flag": target.active_flag,
            "name": target.name,
            "width": target.width,
            "tracking_rating": target.tracking_rating,
            "reco_rating": target.reco_rating,
        }
        date = email.utils.formatdate(None, localtime=False, usegmt=True)

        body = {
            "result_code": ResultCodes.SUCCESS.value,
            "transaction_id": uuid.uuid4().hex,
            "target_record": target_record,
            "status": target.status,
        }
        body_json = json_dump(body)
        context.headers = {
            "Connection": "keep-alive",
            "Content-Length": str(len(body_json)),
            "Content-Type": "application/json",
            "Date": date,
            "server": "envoy",
            "x-envoy-upstream-service-time": "5",
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }
        return body_json

    @route(
        path_pattern=f"/duplicates/{_TARGET_ID_PATTERN}",
        http_methods={GET},
    )
    def get_duplicates(self, request: Request, context: Context) -> str:
        """
        Get targets which may be considered duplicates of a given target.

        Fake implementation of
        https://library.vuforia.com/web-api/cloud-targets-web-services-api#check
        """
        try:
            run_services_validators(
                request_headers=request.headers,
                request_body=request.body,
                request_method=request.method,
                request_path=request.path,
                databases=self._target_manager.databases,
            )
        except ValidatorException as exc:
            context.headers = exc.headers
            context.status_code = exc.status_code
            return exc.response_text

        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self._target_manager.databases,
        )
        target_id = request.path.split("/")[-1]
        target = database.get_target(target_id=target_id)

        other_targets = database.targets - {target}

        similar_targets: list[str] = [
            other.target_id
            for other in other_targets
            if self._duplicate_match_checker(
                first_image_content=target.image_value,
                second_image_content=other.image_value,
            )
            and TargetStatuses.FAILED.value
            not in {target.status, other.status}
            and TargetStatuses.PROCESSING.value != other.status
            and other.active_flag
        ]

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        body = {
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.SUCCESS.value,
            "similar_targets": similar_targets,
        }
        body_json = json_dump(body)
        context.headers = {
            "Connection": "keep-alive",
            "Content-Length": str(len(body_json)),
            "Content-Type": "application/json",
            "Date": date,
            "server": "envoy",
            "x-envoy-upstream-service-time": "5",
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }

        return body_json

    @route(
        path_pattern=f"/targets/{_TARGET_ID_PATTERN}",
        http_methods={PUT},
    )
    def update_target(self, request: Request, context: Context) -> str:
        """
        Update a target.

        Fake implementation of
        https://library.vuforia.com/web-api/cloud-targets-web-services-api#update
        """
        try:
            run_services_validators(
                request_headers=request.headers,
                request_body=request.body,
                request_method=request.method,
                request_path=request.path,
                databases=self._target_manager.databases,
            )
        except ValidatorException as exc:
            context.headers = exc.headers
            context.status_code = exc.status_code
            return exc.response_text

        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self._target_manager.databases,
        )

        target_id = request.path.split("/")[-1]
        target = database.get_target(target_id=target_id)
        body: dict[str, str] = {}

        date = email.utils.formatdate(None, localtime=False, usegmt=True)

        if target.status != TargetStatuses.SUCCESS.value:
            exception = TargetStatusNotSuccess()
            context.headers = exception.headers
            context.status_code = exception.status_code
            return exception.response_text

        width = request.json().get("width", target.width)
        name = request.json().get("name", target.name)
        active_flag = request.json().get("active_flag", target.active_flag)
        application_metadata = request.json().get(
            "application_metadata",
            target.application_metadata,
        )

        image_value = target.image_value
        if "image" in request.json():
            image_value = base64.b64decode(request.json()["image"])

        if "active_flag" in request.json() and active_flag is None:
            fail_exception = Fail(status_code=HTTPStatus.BAD_REQUEST)
            context.headers = fail_exception.headers
            context.status_code = fail_exception.status_code
            return fail_exception.response_text

        if (
            "application_metadata" in request.json()
            and application_metadata is None
        ):
            fail_exception = Fail(status_code=HTTPStatus.BAD_REQUEST)
            context.headers = fail_exception.headers
            context.status_code = fail_exception.status_code
            return fail_exception.response_text

        gmt = ZoneInfo("GMT")
        last_modified_date = datetime.datetime.now(tz=gmt)

        new_target = dataclasses.replace(
            target,
            name=name,
            width=width,
            active_flag=active_flag,
            application_metadata=application_metadata,
            image_value=image_value,
            last_modified_date=last_modified_date,
        )

        database.targets.remove(target)
        database.targets.add(new_target)

        body = {
            "result_code": ResultCodes.SUCCESS.value,
            "transaction_id": uuid.uuid4().hex,
        }
        body_json = json_dump(body)
        context.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "Content-Length": str(len(body_json)),
            "x-envoy-upstream-service-time": "5",
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }
        return body_json

    @route(path_pattern=f"/summary/{_TARGET_ID_PATTERN}", http_methods={GET})
    def target_summary(self, request: Request, context: Context) -> str:
        """
        Get a summary report for a target.

        Fake implementation of
        https://library.vuforia.com/web-api/cloud-targets-web-services-api#retrieve-report
        """
        try:
            run_services_validators(
                request_headers=request.headers,
                request_body=request.body,
                request_method=request.method,
                request_path=request.path,
                databases=self._target_manager.databases,
            )
        except ValidatorException as exc:
            context.headers = exc.headers
            context.status_code = exc.status_code
            return exc.response_text

        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self._target_manager.databases,
        )
        target_id = request.path.split("/")[-1]
        target = database.get_target(target_id=target_id)

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
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
        body_json = json_dump(body)
        context.headers = {
            "Connection": "keep-alive",
            "Content-Length": str(len(body_json)),
            "Content-Type": "application/json",
            "Date": date,
            "server": "envoy",
            "x-envoy-upstream-service-time": "5",
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }

        return body_json
