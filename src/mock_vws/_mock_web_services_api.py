"""
A fake implementation of the Vuforia Web Services API.

See
https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API
"""

import base64
import datetime
import io
import random
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import pytz
import wrapt
from PIL import Image
from requests import codes
from requests_mock import DELETE, GET, POST, PUT
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._constants import ResultCodes, TargetStatuses
from mock_vws._database import VuforiaDatabase
from mock_vws._mock_common import (
    Route,
    get_database_matching_server_keys,
    json_dump,
    set_content_length_header,
)

from ._target import Target
from ._validators import (
    validate_active_flag,
    validate_auth_header_exists,
    validate_authorization,
    validate_date_format,
    validate_date_header_given,
    validate_date_in_range,
    validate_image_color_space,
    validate_image_data_type,
    validate_image_encoding,
    validate_image_format,
    validate_image_is_image,
    validate_image_size,
    validate_keys,
    validate_metadata_encoding,
    validate_metadata_size,
    validate_metadata_type,
    validate_name_characters_in_range,
    validate_name_length,
    validate_name_type,
    validate_not_invalid_json,
    validate_project_state,
    validate_width,
)


@wrapt.decorator
def update_request_count(
    wrapped: Callable[..., str],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Add to the request count.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
    """
    instance.request_count += 1
    return wrapped(*args, **kwargs)


@wrapt.decorator
def parse_target_id(
    wrapped: Callable[..., str],
    instance: 'MockVuforiaWebServicesAPI',
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Parse a target ID in a URL path and give the method a target argument.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        If a target ID is given in the path then the wrapped function is given
        an extra argument - the matching target.
        A `NOT_FOUND` response if there is no matching target.
    """
    request, context = args

    split_path = request.path.split('/')

    if len(split_path) == 2:
        return wrapped(*args, **kwargs)

    target_id = split_path[-1]
    database = get_database_matching_server_keys(
        request=request,
        databases=[instance.database],
    )

    assert isinstance(database, VuforiaDatabase)

    try:
        [matching_target] = [
            target for target in database.targets
            if target.target_id == target_id and not target.delete_date
        ]
    except ValueError:
        body: Dict[str, str] = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.UNKNOWN_TARGET.value,
        }
        context.status_code = codes.NOT_FOUND
        return json_dump(body)

    new_args = args + (matching_target, )
    return wrapped(*new_args, **kwargs)


ROUTES = set([])


def route(
    path_pattern: str,
    http_methods: List[str],
    mandatory_keys: Optional[Set[str]] = None,
    optional_keys: Optional[Set[str]] = None,
) -> Callable[..., Callable]:
    """
    Register a decorated method so that it can be recognized as a route.

    Args:
        path_pattern: The end part of a URL pattern. E.g. `/targets` or
            `/targets/.+`.
        http_methods: HTTP methods that map to the route function.
        mandatory_keys: Keys required by the endpoint.
        optional_keys: Keys which are not required by the endpoint but which
            are allowed.
    """

    def decorator(method: Callable[..., str]) -> Callable[..., str]:
        """
        Register a decorated method so that it can be recognized as a route.

        Args:
            method: Method to register.

        Returns:
            The given `method` with multiple changes, including added
            validators.
        """
        ROUTES.add(
            Route(
                route_name=method.__name__,
                path_pattern=path_pattern,
                http_methods=http_methods,
            ),
        )

        key_validator = validate_keys(
            optional_keys=optional_keys or set([]),
            mandatory_keys=mandatory_keys or set([]),
        )

        # There is an undocumented difference in behavior between `/summary`
        # and other endpoints.
        if path_pattern == '/summary':
            decorators = [
                validate_authorization,
                key_validator,
                validate_not_invalid_json,
                validate_date_in_range,
                validate_date_format,
                validate_date_header_given,
            ]
        else:
            decorators = [
                parse_target_id,
                validate_project_state,
                validate_authorization,
                validate_metadata_size,
                validate_metadata_encoding,
                validate_metadata_type,
                validate_active_flag,
                validate_image_size,
                validate_image_color_space,
                validate_image_format,
                validate_image_is_image,
                validate_image_encoding,
                validate_image_data_type,
                validate_name_characters_in_range,
                validate_name_length,
                validate_name_type,
                validate_width,
                key_validator,
                validate_date_in_range,
                validate_date_format,
                validate_date_header_given,
                validate_not_invalid_json,
            ]

        common_decorators = [
            validate_auth_header_exists,
            set_content_length_header,
            update_request_count,
        ]

        for decorator in decorators + common_decorators:
            method = decorator(method)

        return method

    return decorator


class MockVuforiaWebServicesAPI:
    """
    A fake implementation of the Vuforia Web Services API.

    This implementation is tied to the implementation of `requests_mock`.
    """

    def __init__(
        self,
        vuforia_database: VuforiaDatabase,
        processing_time_seconds: Union[int, float],
    ) -> None:
        """
        Args:
            vuforia_database: A Vuforia database.
            processing_time_seconds: The number of seconds to process each
                image for. In the real Vuforia Web Services, this is not
                deterministic.

        Attributes:
            database (VuforiaDatabase): A Vuforia database.
            routes: The `Route`s to be used in the mock.
            request_count: The number of requests made to this API.
        """
        self.database = vuforia_database
        self.routes: Set[Route] = ROUTES
        self._processing_time_seconds = processing_time_seconds
        self.request_count = 0

    @route(
        path_pattern='/targets',
        http_methods=[POST],
        mandatory_keys={'image', 'width', 'name'},
        optional_keys={'active_flag', 'application_metadata'},
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
        name = request.json()['name']
        database = get_database_matching_server_keys(
            request=request,
            databases=[self.database],
        )

        assert isinstance(database, VuforiaDatabase)

        targets = (
            target for target in database.targets if not target.delete_date
        )
        if any(target.name == name for target in targets):
            context.status_code = codes.FORBIDDEN
            body = {
                'transaction_id': uuid.uuid4().hex,
                'result_code': ResultCodes.TARGET_NAME_EXIST.value,
            }
            return json_dump(body)

        active_flag = request.json().get('active_flag')
        if active_flag is None:
            active_flag = True

        image = request.json()['image']
        decoded = base64.b64decode(image)
        image_file = io.BytesIO(decoded)

        new_target = Target(
            name=request.json()['name'],
            width=request.json()['width'],
            image=image_file,
            active_flag=active_flag,
            processing_time_seconds=self._processing_time_seconds,
            application_metadata=request.json().get('application_metadata'),
        )
        database.targets.append(new_target)

        context.status_code = codes.CREATED
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.TARGET_CREATED.value,
            'target_id': new_target.target_id,
        }
        return json_dump(body)

    @route(path_pattern='/targets/.+', http_methods=[DELETE])
    def delete_target(
        self,
        request: _RequestObjectProxy,  # pylint: disable=unused-argument
        context: _Context,
        target: Target,
    ) -> str:
        """
        Delete a target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Delete-a-Target
        """
        body: Dict[str, str] = {}

        if target.status == TargetStatuses.PROCESSING.value:
            context.status_code = codes.FORBIDDEN
            body = {
                'transaction_id': uuid.uuid4().hex,
                'result_code': ResultCodes.TARGET_STATUS_PROCESSING.value,
            }
            return json_dump(body)

        gmt = pytz.timezone('GMT')
        now = datetime.datetime.now(tz=gmt)
        target.delete_date = now

        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.SUCCESS.value,
        }
        return json_dump(body)

    @route(path_pattern='/summary', http_methods=[GET])
    def database_summary(
        self,
        request: _RequestObjectProxy,  # pylint: disable=unused-argument
        context: _Context,  # pylint: disable=unused-argument
    ) -> str:
        """
        Get a database summary report.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Get-a-Database-Summary-Report
        """
        body: Dict[str, Union[str, int]] = {}

        database = get_database_matching_server_keys(
            request=request,
            databases=[self.database],
        )

        assert isinstance(database, VuforiaDatabase)
        active_images = len(
            [
                target for target in database.targets
                if target.status == TargetStatuses.SUCCESS.value
                and target.active_flag and not target.delete_date
            ],
        )

        failed_images = len(
            [
                target for target in database.targets
                if target.status == TargetStatuses.FAILED.value
                and not target.delete_date
            ],
        )

        inactive_images = len(
            [
                target for target in database.targets
                if target.status == TargetStatuses.SUCCESS.value
                and not target.active_flag and not target.delete_date
            ],
        )

        processing_images = len(
            [
                target for target in database.targets
                if target.status == TargetStatuses.PROCESSING.value
                and not target.delete_date
            ],
        )

        body = {
            'result_code': ResultCodes.SUCCESS.value,
            'transaction_id': uuid.uuid4().hex,
            'name': database.database_name,
            'active_images': active_images,
            'inactive_images': inactive_images,
            'failed_images': failed_images,
            'target_quota': 1000,
            'total_recos': 0,
            'current_month_recos': 0,
            'previous_month_recos': 0,
            'processing_images': processing_images,
            'reco_threshold': 1000,
            'request_quota': 100000,
            'request_usage': self.request_count,
        }
        return json_dump(body)

    @route(path_pattern='/targets', http_methods=[GET])
    def target_list(
        self,
        request: _RequestObjectProxy,  # pylint: disable=unused-argument
        context: _Context,  # pylint: disable=unused-argument
    ) -> str:
        """
        Get a list of all targets.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Get-a-Target-List-for-a-Cloud-Database
        """
        database = get_database_matching_server_keys(
            request=request,
            databases=[self.database],
        )

        assert isinstance(database, VuforiaDatabase)
        results = [
            target.target_id for target in database.targets
            if not target.delete_date
        ]

        body: Dict[str, Union[str, List[str]]] = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.SUCCESS.value,
            'results': results,
        }
        return json_dump(body)

    @route(path_pattern='/targets/.+', http_methods=[GET])
    def get_target(
        self,
        request: _RequestObjectProxy,  # pylint: disable=unused-argument
        context: _Context,  # pylint: disable=unused-argument
        target: Target,
    ) -> str:
        """
        Get details of a target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Retrieve-a-Target-Record
        """
        target_record = {
            'target_id': target.target_id,
            'active_flag': target.active_flag,
            'name': target.name,
            'width': target.width,
            'tracking_rating': target.tracking_rating,
            'reco_rating': target.reco_rating,
        }

        body = {
            'result_code': ResultCodes.SUCCESS.value,
            'transaction_id': uuid.uuid4().hex,
            'target_record': target_record,
            'status': target.status,
        }
        return json_dump(body)

    @route(path_pattern='/duplicates/.+', http_methods=[GET])
    def get_duplicates(
        self,
        request: _RequestObjectProxy,  # pylint: disable=unused-argument
        context: _Context,  # pylint: disable=unused-argument
        target: Target,
    ) -> str:
        """
        Get targets which may be considered duplicates of a given target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Check-for-Duplicate-Targets
        """
        database = get_database_matching_server_keys(
            request=request,
            databases=[self.database],
        )

        assert isinstance(database, VuforiaDatabase)
        other_targets = set(database.targets) - set([target])

        similar_targets: List[str] = [
            other.target_id for other in other_targets
            if Image.open(other.image) == Image.open(target.image) and
            TargetStatuses.FAILED.value not in (target.status, other.status)
            and TargetStatuses.PROCESSING.value != other.status
            and other.active_flag
        ]

        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.SUCCESS.value,
            'similar_targets': similar_targets,
        }

        return json_dump(body)

    @route(
        path_pattern='/targets/.+',
        http_methods=[PUT],
        optional_keys={
            'active_flag',
            'application_metadata',
            'image',
            'name',
            'width',
        },
    )
    def update_target(
        self,
        request: _RequestObjectProxy,
        context: _Context,
        target: Target,
    ) -> str:
        """
        Update a target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Update-a-Target
        """
        body: Dict[str, str] = {}
        database = get_database_matching_server_keys(
            request=request,
            databases=[self.database],
        )

        assert isinstance(database, VuforiaDatabase)

        if target.status != TargetStatuses.SUCCESS.value:
            context.status_code = codes.FORBIDDEN
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
                body = {
                    'transaction_id': uuid.uuid4().hex,
                    'result_code': ResultCodes.FAIL.value,
                }
                context.status_code = codes.BAD_REQUEST
                return json_dump(body)
            target.active_flag = active_flag

        if 'application_metadata' in request.json():
            if request.json()['application_metadata'] is None:
                body = {
                    'transaction_id': uuid.uuid4().hex,
                    'result_code': ResultCodes.FAIL.value,
                }
                context.status_code = codes.BAD_REQUEST
                return json_dump(body)
            application_metadata = request.json()['application_metadata']
            target.application_metadata = application_metadata

        if 'name' in request.json():
            name = request.json()['name']
            other_targets = set(database.targets) - set([target])
            if any(
                other.name == name for other in other_targets
                if not other.delete_date
            ):
                context.status_code = codes.FORBIDDEN
                body = {
                    'transaction_id': uuid.uuid4().hex,
                    'result_code': ResultCodes.TARGET_NAME_EXIST.value,
                }
                return json_dump(body)
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

        gmt = pytz.timezone('GMT')
        now = datetime.datetime.now(tz=gmt)
        target.last_modified_date = now

        body = {
            'result_code': ResultCodes.SUCCESS.value,
            'transaction_id': uuid.uuid4().hex,
        }
        return json_dump(body)

    @route(path_pattern='/summary/.+', http_methods=[GET])
    def target_summary(
        self,
        request: _RequestObjectProxy,  # pylint: disable=unused-argument
        context: _Context,  # pylint: disable=unused-argument
        target: Target,
    ) -> str:
        """
        Get a summary report for a target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Retrieve-a-Target-Summary-Report
        """
        database = get_database_matching_server_keys(
            request=request,
            databases=[self.database],
        )

        assert isinstance(database, VuforiaDatabase)
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
