"""
A fake implementation of the Vuforia Web Services API.

See
https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API
"""

import base64
import datetime
import io
import itertools
import random
import uuid
from http import HTTPStatus
from typing import Any, Callable, Dict, List, Set, Tuple, Union

import wrapt
from backports.zoneinfo import ZoneInfo
from PIL import Image
from requests_mock import DELETE, GET, POST, PUT
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._constants import ResultCodes, TargetStatuses
from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._mock_common import (
    Route,
    json_dump,
    set_content_length_header,
    set_date_header,
)
from mock_vws._services_validators import run_services_validators
from mock_vws._services_validators.exceptions import (
    AuthenticationFailure,
    BadImage,
    ContentLengthHeaderNotInt,
    ContentLengthHeaderTooLarge,
    Fail,
    ImageTooLarge,
    MetadataTooLarge,
    OopsErrorOccurredResponse,
    ProjectInactive,
    RequestTimeTooSkewed,
    TargetNameExist,
    UnknownTarget,
    UnnecessaryRequestBody,
)
from mock_vws.database import VuforiaDatabase
from mock_vws.target import Target

_TARGET_ID_PATTERN = '[A-Za-z0-9]+'


@wrapt.decorator
def run_validators(
    wrapped: Callable[..., str],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Send a relevant response if any validator raises an exception.

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
        run_services_validators(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=instance.databases,
        )
    except (
        UnknownTarget,
        ProjectInactive,
        AuthenticationFailure,
        Fail,
        MetadataTooLarge,
        TargetNameExist,
        BadImage,
        ImageTooLarge,
        RequestTimeTooSkewed,
        ContentLengthHeaderTooLarge,
        ContentLengthHeaderNotInt,
        OopsErrorOccurredResponse,
        UnnecessaryRequestBody,
    ) as exc:
        context.headers = exc.headers
        context.status_code = exc.status_code
        return exc.response_text

    try:
        return wrapped(*args, **kwargs)
    except Fail as exc:
        context.headers = exc.headers
        context.status_code = exc.status_code
        return exc.response_text


ROUTES = set([])


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
            # See https://github.com/PyCQA/pylint/issues/259
            method = decorator(  # pylint: disable=no-value-for-parameter
                method,
            )

        return method

    return decorator


def _get_target_from_request(
    request_path: str,
    databases: Set[VuforiaDatabase],
) -> Target:
    """
    Given a request path with a target ID in the path, and a list of databases,
    return the target with that ID from those databases.
    """
    split_path = request_path.split('/')
    target_id = split_path[-1]
    all_database_targets = itertools.chain.from_iterable(
        [database.targets for database in databases],
    )
    [target] = [
        target
        for target in all_database_targets
        if target.target_id == target_id
    ]
    return target


class MockVuforiaWebServicesAPI:
    """
    A fake implementation of the Vuforia Web Services API.

    This implementation is tied to the implementation of `requests_mock`.
    """

    def __init__(
        self,
        processing_time_seconds: Union[int, float],
    ) -> None:
        """
        Args:
            processing_time_seconds: The number of seconds to process each
                image for. In the real Vuforia Web Services, this is not
                deterministic.

        Attributes:
            databases: Target databases.
            routes: The `Route`s to be used in the mock.
        """
        self.databases: Set[VuforiaDatabase] = set([])
        self.routes: Set[Route] = ROUTES
        self._processing_time_seconds = processing_time_seconds

    @route(
        path_pattern='/targets',
        http_methods={POST},
    )
    def add_target(
        self,
        request: _RequestObjectProxy,
        context: _Context,
    ) -> str:
        """
        Add a target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Add-a-Target
        """
        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self.databases,
        )

        assert isinstance(database, VuforiaDatabase)

        given_active_flag = request.json().get('active_flag')
        active_flag = {
            None: True,
            True: True,
            False: False,
        }[given_active_flag]

        image = request.json()['image']
        decoded = base64.b64decode(image)
        image_file = io.BytesIO(decoded)

        name = request.json()['name']
        width = request.json()['width']
        application_metadata = request.json().get('application_metadata')

        new_target = Target(
            name=name,
            width=width,
            image=image_file,
            active_flag=active_flag,
            processing_time_seconds=self._processing_time_seconds,
            application_metadata=application_metadata,
        )
        database.targets.add(new_target)

        context.headers = {
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Server': 'nginx',
        }
        context.status_code = HTTPStatus.CREATED
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.TARGET_CREATED.value,
            'target_id': new_target.target_id,
        }
        return json_dump(body)

    @route(
        path_pattern=f'/targets/{_TARGET_ID_PATTERN}',
        http_methods={DELETE},
    )
    def delete_target(
        self,
        request: _RequestObjectProxy,
        context: _Context,
    ) -> str:
        """
        Delete a target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Delete-a-Target
        """
        body: Dict[str, str] = {}
        target = _get_target_from_request(
            request_path=request.path,
            databases=self.databases,
        )
        context.headers = {
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Server': 'nginx',
        }

        if target.status == TargetStatuses.PROCESSING.value:
            context.status_code = HTTPStatus.FORBIDDEN
            body = {
                'transaction_id': uuid.uuid4().hex,
                'result_code': ResultCodes.TARGET_STATUS_PROCESSING.value,
            }
            return json_dump(body)

        target.delete()

        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.SUCCESS.value,
        }
        return json_dump(body)

    @route(path_pattern='/summary', http_methods={GET})
    def database_summary(
        self,
        request: _RequestObjectProxy,
        context: _Context,  # pylint: disable=unused-argument
    ) -> str:
        """
        Get a database summary report.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Get-a-Database-Summary-Report
        """
        body: Dict[str, Union[str, int]] = {}

        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self.databases,
        )

        assert isinstance(database, VuforiaDatabase)
        context.headers = {
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Server': 'nginx',
        }
        body = {
            'result_code': ResultCodes.SUCCESS.value,
            'transaction_id': uuid.uuid4().hex,
            'name': database.database_name,
            'active_images': len(database.active_targets),
            'inactive_images': len(database.inactive_targets),
            'failed_images': len(database.failed_targets),
            'target_quota': database.target_quota,
            'total_recos': database.total_recos,
            'current_month_recos': database.current_month_recos,
            'previous_month_recos': database.previous_month_recos,
            'processing_images': len(database.processing_targets),
            'reco_threshold': database.reco_threshold,
            'request_quota': database.request_quota,
            'request_usage': 0,
        }
        return json_dump(body)

    @route(path_pattern='/targets', http_methods={GET})
    def target_list(
        self,
        request: _RequestObjectProxy,
        context: _Context,  # pylint: disable=unused-argument
    ) -> str:
        """
        Get a list of all targets.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Get-a-Target-List-for-a-Cloud-Database
        """
        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self.databases,
        )

        assert isinstance(database, VuforiaDatabase)
        context.headers = {
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Server': 'nginx',
        }

        results = [target.target_id for target in database.not_deleted_targets]
        body: Dict[str, Union[str, List[str]]] = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.SUCCESS.value,
            'results': results,
        }
        return json_dump(body)

    @route(path_pattern=f'/targets/{_TARGET_ID_PATTERN}', http_methods={GET})
    def get_target(
        self,
        request: _RequestObjectProxy,
        context: _Context,  # pylint: disable=unused-argument
    ) -> str:
        """
        Get details of a target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Retrieve-a-Target-Record
        """
        target = _get_target_from_request(
            request_path=request.path,
            databases=self.databases,
        )

        target_record = {
            'target_id': target.target_id,
            'active_flag': target.active_flag,
            'name': target.name,
            'width': target.width,
            'tracking_rating': target.tracking_rating,
            'reco_rating': target.reco_rating,
        }
        context.headers = {
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Server': 'nginx',
        }

        body = {
            'result_code': ResultCodes.SUCCESS.value,
            'transaction_id': uuid.uuid4().hex,
            'target_record': target_record,
            'status': target.status,
        }
        return json_dump(body)

    @route(
        path_pattern=f'/duplicates/{_TARGET_ID_PATTERN}',
        http_methods={GET},
    )
    def get_duplicates(
        self,
        request: _RequestObjectProxy,
        context: _Context,  # pylint: disable=unused-argument
    ) -> str:
        """
        Get targets which may be considered duplicates of a given target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Check-for-Duplicate-Targets
        """
        target = _get_target_from_request(
            request_path=request.path,
            databases=self.databases,
        )
        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self.databases,
        )

        assert isinstance(database, VuforiaDatabase)
        other_targets = set(database.targets) - set([target])

        similar_targets: List[str] = [
            other.target_id
            for other in other_targets
            if Image.open(other.image) == Image.open(target.image)
            and TargetStatuses.FAILED.value
            not in (target.status, other.status)
            and TargetStatuses.PROCESSING.value != other.status
            and other.active_flag
        ]

        context.headers = {
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Server': 'nginx',
        }
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.SUCCESS.value,
            'similar_targets': similar_targets,
        }

        return json_dump(body)

    @route(
        path_pattern=f'/targets/{_TARGET_ID_PATTERN}',
        http_methods={PUT},
    )
    def update_target(
        self,
        request: _RequestObjectProxy,
        context: _Context,
    ) -> str:
        """
        Update a target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Update-a-Target
        """
        target = _get_target_from_request(
            request_path=request.path,
            databases=self.databases,
        )
        body: Dict[str, str] = {}
        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self.databases,
        )

        assert isinstance(database, VuforiaDatabase)
        context.headers = {
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Server': 'nginx',
        }

        if target.status != TargetStatuses.SUCCESS.value:
            context.status_code = HTTPStatus.FORBIDDEN
            body = {
                'transaction_id': uuid.uuid4().hex,
                'result_code': ResultCodes.TARGET_STATUS_NOT_SUCCESS.value,
            }
            return json_dump(body)

        if 'width' in request.json():
            target.width = request.json()['width']

        if 'active_flag' in request.json():
            active_flag = request.json()['active_flag']
            if active_flag is None:
                raise Fail(status_code=HTTPStatus.BAD_REQUEST)

            target.active_flag = active_flag

        if 'application_metadata' in request.json():
            application_metadata = request.json()['application_metadata']
            if application_metadata is None:
                raise Fail(status_code=HTTPStatus.BAD_REQUEST)
            target.application_metadata = application_metadata

        if 'name' in request.json():
            name = request.json()['name']
            target.name = name

        if 'image' in request.json():
            image = request.json()['image']
            decoded = base64.b64decode(image)
            image_file = io.BytesIO(decoded)
            target.image = image_file

        # In the real implementation, the tracking rating can stay the same.
        # However, for demonstration purposes, the tracking rating changes but
        # when the target is updated.
        available_values = list(set(range(6)) - set([target.tracking_rating]))
        target.processed_tracking_rating = random.choice(available_values)

        gmt = ZoneInfo('GMT')
        now = datetime.datetime.now(tz=gmt)
        target.last_modified_date = now

        body = {
            'result_code': ResultCodes.SUCCESS.value,
            'transaction_id': uuid.uuid4().hex,
        }
        return json_dump(body)

    @route(path_pattern=f'/summary/{_TARGET_ID_PATTERN}', http_methods={GET})
    def target_summary(
        self,
        request: _RequestObjectProxy,
        context: _Context,  # pylint: disable=unused-argument
    ) -> str:
        """
        Get a summary report for a target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Retrieve-a-Target-Summary-Report
        """
        target = _get_target_from_request(
            request_path=request.path,
            databases=self.databases,
        )
        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self.databases,
        )

        assert isinstance(database, VuforiaDatabase)
        context.headers = {
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Server': 'nginx',
        }

        body = {
            'status': target.status,
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.SUCCESS.value,
            'database_name': database.database_name,
            'target_name': target.name,
            'upload_date': target.upload_date.strftime('%Y-%m-%d'),
            'active_flag': target.active_flag,
            'tracking_rating': target.tracking_rating,
            'total_recos': 0,
            'current_month_recos': 0,
            'previous_month_recos': 0,
        }
        return json_dump(body)
