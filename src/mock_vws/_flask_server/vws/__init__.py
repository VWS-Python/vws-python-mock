"""
TODO
"""

import base64
import email.utils
import io
import json
import uuid
from http import HTTPStatus
from typing import Dict, List, Tuple, Union, Optional

import requests
from flask import Flask, Response, request
from PIL import Image
from werkzeug.datastructures import Headers
# TODO see if we can go without any werkzeug imports and then no direct requirement
from werkzeug.wsgi import ClosingIterator

from mock_vws._constants import ResultCodes, TargetStatuses
from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._mock_common import json_dump
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
    TargetStatusNotSuccess,
    TargetStatusProcessing,
)
from mock_vws.database import VuforiaDatabase
from mock_vws.target import Target

from ._constants import STORAGE_BASE_URL
from ._databases import get_all_databases

VWS_FLASK_APP = Flask(import_name=__name__)
VWS_FLASK_APP.config['PROPAGATE_EXCEPTIONS'] = True

# We use a custom response type.
# Without this, a content type is added to all responses.
# Some of our responses need to not have a "Content-Type" header.
class ResponseNoContentTypeAdded(Response):
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
            content_type is None and
            self.headers and
            'Content-Type' in self.headers and
            not content_type_from_headers
        ):
            headers_dict = dict(self.headers)
            headers_dict.pop('Content-Type')
            self.headers = Headers(headers_dict)


VWS_FLASK_APP.response_class = ResponseNoContentTypeAdded


@VWS_FLASK_APP.before_request
def validate_request() -> None:
    request.environ['wsgi.input_terminated'] = True
    databases = get_all_databases()
    run_services_validators(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )



@VWS_FLASK_APP.errorhandler(UnknownTarget)
@VWS_FLASK_APP.errorhandler(ProjectInactive)
@VWS_FLASK_APP.errorhandler(AuthenticationFailure)
@VWS_FLASK_APP.errorhandler(Fail)
@VWS_FLASK_APP.errorhandler(MetadataTooLarge)
@VWS_FLASK_APP.errorhandler(TargetNameExist)
@VWS_FLASK_APP.errorhandler(BadImage)
@VWS_FLASK_APP.errorhandler(ImageTooLarge)
@VWS_FLASK_APP.errorhandler(RequestTimeTooSkewed)
@VWS_FLASK_APP.errorhandler(ContentLengthHeaderTooLarge)
@VWS_FLASK_APP.errorhandler(ContentLengthHeaderNotInt)
@VWS_FLASK_APP.errorhandler(UnnecessaryRequestBody)
@VWS_FLASK_APP.errorhandler(OopsErrorOccurredResponse)
@VWS_FLASK_APP.errorhandler(TargetStatusProcessing)
@VWS_FLASK_APP.errorhandler(TargetStatusNotSuccess)
# TODO update name and type hint here
def handle_unknown_target(e: UnknownTarget) -> Response:
    return ResponseNoContentTypeAdded(
        status=e.status_code.value,
        response=e.response_text,
        headers=e.headers,
    )


@VWS_FLASK_APP.route('/targets', methods=['POST'])
def add_target() -> Response:
    """
    Add a target.

    Fake implementation of
    https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Add-a-Target
    """
    # We do not use ``request.get_json(force=True)`` because this only works
    # when the content type is given as ``application/json``.
    request_json = json.loads(request.data)
    name = request_json['name']
    databases = get_all_databases()
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )

    assert isinstance(database, VuforiaDatabase)

    active_flag = request_json.get('active_flag')
    if active_flag is None:
        active_flag = True

    image = request_json['image']
    decoded = base64.b64decode(image)
    image_file = io.BytesIO(decoded)

    new_target = Target(
        name=name,
        width=request_json['width'],
        image=image_file,
        active_flag=active_flag,
        processing_time_seconds=0.2,
        # TODO add this back:
        # processing_time_seconds=self._processing_time_seconds,
        application_metadata=request_json.get('application_metadata'),
    )

    requests.post(
        url=f'{STORAGE_BASE_URL}/databases/{database.database_name}/targets',
        json=new_target.to_dict(),
    )

    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    headers = {
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Server': 'nginx',
        'Date': date,
    }
    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.TARGET_CREATED.value,
        'target_id': new_target.target_id,
    }

    return Response(
        status=HTTPStatus.CREATED,
        response=json_dump(body),
        headers=headers,
    )


@VWS_FLASK_APP.route('/targets/<string:target_id>', methods=['GET'])
def get_target(target_id: str) -> Response:
    """
    Get details of a target.

    Fake implementation of
    https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Retrieve-a-Target-Record
    """
    databases = get_all_databases()
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )

    assert isinstance(database, VuforiaDatabase)
    [target] = [
        target for target in database.targets if target.target_id == target_id
    ]

    target_record = {
        'target_id': target.target_id,
        'active_flag': target.active_flag,
        'name': target.name,
        'width': target.width,
        'tracking_rating': target.tracking_rating,
        'reco_rating': target.reco_rating,
    }

    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    headers = {
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Server': 'nginx',
        'Date': date,
    }
    body = {
        'result_code': ResultCodes.SUCCESS.value,
        'transaction_id': uuid.uuid4().hex,
        'target_record': target_record,
        'status': target.status,
    }
    return Response(
        status=HTTPStatus.OK,
        response=json_dump(body),
        headers=headers,
    )


@VWS_FLASK_APP.route('/targets/<string:target_id>', methods=['DELETE'])
def delete_target(target_id: str) -> Response:
    """
    Delete a target.

    Fake implementation of
    https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Delete-a-Target
    """
    body: Dict[str, str] = {}
    databases = get_all_databases()
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )

    assert isinstance(database, VuforiaDatabase)
    [target] = [
        target for target in database.targets if target.target_id == target_id
    ]

    if target.status == TargetStatuses.PROCESSING.value:
        raise TargetStatusProcessing

    delete_url = (
        f'{STORAGE_BASE_URL}/databases/{database.database_name}/targets/'
        f'{target_id}'
    )
    requests.delete(url=delete_url)

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.SUCCESS.value,
    }
    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    headers = {
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Server': 'nginx',
        'Date': date,
    }
    return Response(
        status=HTTPStatus.OK,
        response=json_dump(body),
        headers=headers,
    )


@VWS_FLASK_APP.route('/summary', methods=['GET'])
def database_summary() -> Response:
    """
    Get a database summary report.

    Fake implementation of
    https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Get-a-Database-Summary-Report
    """
    body: Dict[str, Union[str, int]] = {}

    databases = get_all_databases()
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )

    assert isinstance(database, VuforiaDatabase)
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
        # We have ``self.request_count`` but Vuforia always shows 0.
        # This was not always the case.
        'request_usage': 0,
    }
    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    headers = {
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Server': 'nginx',
        'Date': date,
    }
    return Response(
        status=HTTPStatus.OK,
        response=json_dump(body),
        headers=headers,
    )


@VWS_FLASK_APP.route('/summary/<string:target_id>', methods=['GET'])
def target_summary(target_id: str) -> Response:
    """
    Get a summary report for a target.

    Fake implementation of
    https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Retrieve-a-Target-Summary-Report
    """
    databases = get_all_databases()
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )

    assert isinstance(database, VuforiaDatabase)
    [target] = [
        target for target in database.targets if target.target_id == target_id
    ]
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
    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    headers = {
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Server': 'nginx',
        'Date': date,
    }
    return Response(
        status=HTTPStatus.OK,
        response=json_dump(body),
        headers=headers,
    )


@VWS_FLASK_APP.route('/duplicates/<string:target_id>', methods=['GET'])
def get_duplicates(target_id: str) -> Response:
    """
    Get targets which may be considered duplicates of a given target.

    Fake implementation of
    https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Check-for-Duplicate-Targets
    """
    databases = get_all_databases()
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )

    assert isinstance(database, VuforiaDatabase)
    [target] = [
        target for target in database.targets if target.target_id == target_id
    ]
    other_targets = set(database.targets) - set([target])

    similar_targets: List[str] = [
        other.target_id
        for other in other_targets
        if Image.open(other.image) == Image.open(target.image)
        and TargetStatuses.FAILED.value not in (target.status, other.status)
        and TargetStatuses.PROCESSING.value != other.status
        and other.active_flag
    ]

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.SUCCESS.value,
        'similar_targets': similar_targets,
    }

    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    headers = {
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Server': 'nginx',
        'Date': date,
    }
    return Response(
        status=HTTPStatus.OK,
        response=json_dump(body),
        headers=headers,
    )


@VWS_FLASK_APP.route('/targets', methods=['GET'])
def target_list() -> Response:
    """
    Get a list of all targets.

    Fake implementation of
    https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Get-a-Target-List-for-a-Cloud-Database
    """
    databases = get_all_databases()
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )
    assert isinstance(database, VuforiaDatabase)
    results = [target.target_id for target in database.not_deleted_targets]

    body: Dict[str, Union[str, List[str]]] = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.SUCCESS.value,
        'results': results,
    }
    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    headers = {
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Server': 'nginx',
        'Date': date,
    }
    return Response(
        status=HTTPStatus.OK,
        response=json_dump(body),
        headers=headers,
    )


@VWS_FLASK_APP.route('/targets/<string:target_id>', methods=['PUT'])
def update_target(target_id: str) -> Response:
    """
    Update a target.

    Fake implementation of
    https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Update-a-Target
    """
    # We do not use ``request.get_json(force=True)`` because this only works
    # when the content type is given as ``application/json``.
    request_json = json.loads(request.data)
    body: Dict[str, str] = {}
    databases = get_all_databases()
    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )

    assert isinstance(database, VuforiaDatabase)
    [target] = [
        target for target in database.targets if target.target_id == target_id
    ]

    if target.status != TargetStatuses.SUCCESS.value:
        raise TargetStatusNotSuccess

    update_values = {}
    if 'width' in request_json:
        update_values['width'] = request_json['width']

    if 'active_flag' in request_json:
        active_flag = request_json['active_flag']
        if active_flag is None:
            raise Fail(status_code=HTTPStatus.BAD_REQUEST)
        update_values['active_flag'] = active_flag

    if 'application_metadata' in request_json:
        application_metadata = request_json['application_metadata']
        if application_metadata is None:
            raise Fail(status_code=HTTPStatus.BAD_REQUEST)
        update_values['application_metadata'] = application_metadata

    if 'name' in request_json:
        name = request_json['name']
        update_values['name'] = name

    if 'image' in request_json:
        image = request_json['image']
        update_values['image'] = image

    put_url = (
        f'{STORAGE_BASE_URL}/databases/{database.database_name}/targets/'
        f'{target_id}'
    )
    requests.put(url=put_url, json=update_values)

    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    headers = {
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Server': 'nginx',
        'Date': date,
    }
    body = {
        'result_code': ResultCodes.SUCCESS.value,
        'transaction_id': uuid.uuid4().hex,
    }
    return Response(
        status=HTTPStatus.OK,
        response=json_dump(body),
        headers=headers,
    )
