"""
A fake implementation of the Vuforia Web Query API.

See
https://library.vuforia.com/articles/Solution/How-To-Perform-an-Image-Recognition-Query
"""

import cgi
import datetime
import io
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Set, Union

import pytz
from requests import codes
from requests_mock import POST
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._constants import ResultCodes, TargetStatuses
from mock_vws._database import VuforiaDatabase
from mock_vws._mock_common import (
    Route,
    json_dump,
    parse_multipart,
    set_content_length_header,
)
from mock_vws._mock_web_services_api import Target

from ._query_validators import (
    validate_accept_header,
    validate_content_type_header,
    validate_date_format,
    validate_date_header_given,
    validate_date_in_range,
    validate_extra_fields,
    validate_image_field_given,
    validate_image_file_contents,
    validate_image_file_size,
    validate_image_format,
    validate_include_target_data,
    validate_max_num_results,
    validate_project_state,
)
from ._validators import validate_auth_header_exists, validate_authorization

ROUTES = set([])


def route(
    path_pattern: str,
    http_methods: List[str],
) -> Callable[..., Callable]:
    """
    Register a decorated method so that it can be recognized as a route.

    Args:
        path_pattern: The end part of a URL pattern. E.g. `/targets` or
            `/targets/.+`.
        http_methods: HTTP methods that map to the route function.
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

        decorators = [
            validate_authorization,
            validate_date_in_range,
            validate_date_format,
            validate_date_header_given,
            validate_include_target_data,
            validate_max_num_results,
            validate_image_file_size,
            validate_image_file_contents,
            validate_image_format,
            validate_image_field_given,
            validate_extra_fields,
            validate_content_type_header,
            validate_accept_header,
            validate_auth_header_exists,
            validate_project_state,
            set_content_length_header,
        ]

        for decorator in decorators:
            method = decorator(method)

        return method

    return decorator


class MockVuforiaWebQueryAPI:
    """
    A fake implementation of the Vuforia Web Query API.

    This implementation is tied to the implementation of `requests_mock`.
    """

    def __init__(
        self,
        vuforia_database: VuforiaDatabase,
        query_recognizes_deletion_seconds: Union[int, float],
    ) -> None:
        """
        Args:
            vuforia_database: A Vuforia database.
            query_recognizes_deletion_seconds: The number of seconds after a
                target has been deleted that the query endpoint will return a
                500 response for on a match.

        Attributes:
            routes: The `Route`s to be used in the mock.
            access_key (str): A VWS client access key.
            secret_key (str): A VWS client secret key.
            database (VuforiaDatabase): An instance of a mock web services API.
        """
        self.routes: Set[Route] = ROUTES
        self.access_key: bytes = vuforia_database.client_access_key
        self.secret_key: bytes = vuforia_database.client_secret_key
        self.database = vuforia_database
        self._query_recognizes_deletion_seconds = (
            query_recognizes_deletion_seconds
        )

    @route(path_pattern='/v1/query', http_methods=[POST])
    def query(
        self,
        request: _RequestObjectProxy,
        context: _Context,
    ) -> str:
        """
        Perform an image recognition query.
        """
        body_file = io.BytesIO(request.body)

        _, pdict = cgi.parse_header(request.headers['Content-Type'])
        parsed = parse_multipart(
            fp=body_file,
            pdict={
                'boundary': pdict['boundary'].encode(),
            },
        )

        [max_num_results] = parsed.get('max_num_results', ['1'])

        [include_target_data] = parsed.get('include_target_data', ['top'])
        include_target_data = include_target_data.lower()

        [image] = parsed['image']
        matches: Set[Target] = set([])
        gmt = pytz.timezone('GMT')
        now = datetime.datetime.now(tz=gmt)

        minimum_time_since_delete = datetime.timedelta(
            seconds=self._query_recognizes_deletion_seconds,
        )

        for target in self.database.targets:
            delete_processing = bool(
                target.delete_date
                and (now - target.delete_date) < minimum_time_since_delete,
            )
            if target.image.getvalue() == image:
                if target.status == TargetStatuses.PROCESSING.value:
                    # We return an example 500 response.
                    # Each response given by Vuforia is different.
                    #
                    # Sometimes Vuforia will do the equivalent of `continue`
                    # here, but we choose to:
                    # * Do the most unexpected thing.
                    # * Be consistent with every response.
                    resources_dir = Path(__file__).parent / 'resources'
                    filename = 'match_processing_response'
                    match_processing_resp_file = resources_dir / filename
                    context.status_code = codes.INTERNAL_SERVER_ERROR
                    cache_control = 'must-revalidate,no-cache,no-store'
                    context.headers['Cache-Control'] = cache_control
                    content_type = 'text/html; charset=ISO-8859-1'
                    context.headers['Content-Type'] = content_type
                    return Path(match_processing_resp_file).read_text()
                if target.active_flag and delete_processing:
                    # We return an example 500 response.
                    # Each response given by Vuforia is different.
                    resources_dir = Path(__file__).parent / 'resources'
                    filename = 'match_processing_response'
                    match_processing_resp_file = resources_dir / filename
                    context.status_code = codes.INTERNAL_SERVER_ERROR
                    cache_control = 'must-revalidate,no-cache,no-store'
                    context.headers['Cache-Control'] = cache_control
                    content_type = 'text/html; charset=ISO-8859-1'
                    context.headers['Content-Type'] = content_type
                    return Path(match_processing_resp_file).read_text()
                if (
                    target.active_flag and not target.delete_date
                    and target.status == TargetStatuses.SUCCESS.value
                ):
                    matches.add(target)

        results: List[Dict[str, Any]] = []
        for target in matches:
            target_timestamp = target.last_modified_date.timestamp()
            target_data = {
                'target_timestamp': int(target_timestamp),
                'name': target.name,
                'application_metadata': target.application_metadata,
            }

            if include_target_data == 'all':
                result = {
                    'target_id': target.target_id,
                    'target_data': target_data,
                }
            elif include_target_data == 'top' and not results:
                result = {
                    'target_id': target.target_id,
                    'target_data': target_data,
                }
            else:
                result = {
                    'target_id': target.target_id,
                }

            results.append(result)

        body = {
            'result_code': ResultCodes.SUCCESS.value,
            'results': results[:int(max_num_results)],
            'query_id': uuid.uuid4().hex,
        }

        value = json_dump(body)
        return value
