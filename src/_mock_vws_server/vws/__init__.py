import base64
import email.utils
import io
import json
import uuid
from typing import Dict, List, Tuple, Union

import requests
from flask import Flask, Response, request
from flask_json_schema import JsonSchema, JsonValidationError
from PIL import Image
from requests import codes

from mock_vws._constants import ResultCodes, TargetStatuses
from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._mock_common import json_dump
from mock_vws.database import VuforiaDatabase
from mock_vws.target import Target

from ._constants import STORAGE_BASE_URL
from ._databases import get_all_databases
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
from pathlib import Path

VWS_FLASK_APP = Flask(__name__)

@VWS_FLASK_APP.before_request
def validate_request() -> None:
    databases = get_all_databases()
    run_services_validators(
        request_text=request.data.decode(),
        request_headers=dict(request.headers),
        # TODO not sure about this one
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )
    # decorators = [
    #     # parse_target_id,
    #     # update_request_count,
    # ]


@VWS_FLASK_APP.errorhandler(UnknownTarget)
def handle_unknown_target(e: UnknownTarget) -> Tuple[str, int]:
    return e.response_text, e.status_code

@VWS_FLASK_APP.errorhandler(ProjectInactive)
def handle_project_inactive(e: ProjectInactive) -> Tuple[str, int]:
    return e.response_text, e.status_code

@VWS_FLASK_APP.errorhandler(AuthenticationFailure)
def handle_authentication_failure(e: AuthenticationFailure) -> Tuple[str, int]:
    return e.response_text, e.status_code

@VWS_FLASK_APP.errorhandler(Fail)
def handle_fail(e: Fail) -> Tuple[str, int]:
    return e.response_text, e.status_code

@VWS_FLASK_APP.errorhandler(MetadataTooLarge)
def handle_metadata_too_large(e: MetadataTooLarge) -> Tuple[str, int]:
    return e.response_text, e.status_code

@VWS_FLASK_APP.errorhandler(TargetNameExist)
def handle_target_name_exist(e: TargetNameExist) -> Tuple[str, int]:
    return e.response_text, e.status_code

@VWS_FLASK_APP.errorhandler(BadImage)
def handle_bad_image(e: BadImage) -> Tuple[str, int]:
    return e.response_text, e.status_code

@VWS_FLASK_APP.errorhandler(ImageTooLarge)
def handle_image_too_large(e: ImageTooLarge) -> Tuple[str, int]:
    return e.response_text, e.status_code

@VWS_FLASK_APP.errorhandler(RequestTimeTooSkewed)
def handle_request_time_too_skewed(e: RequestTimeTooSkewed) -> Tuple[str, int]:
    return e.response_text, e.status_code

@VWS_FLASK_APP.errorhandler(OopsErrorOccurredResponse)
def handle_oops_error_occurred(e: OopsErrorOccurredResponse) -> Tuple[str, int]:
    resources_dir = Path(__file__).parent / 'resources'
    filename = 'oops_error_occurred_response.html'
    oops_resp_file = resources_dir / filename
    content_type = 'text/html; charset=UTF-8'
    context.headers['Content-Type'] = content_type
    text = str(oops_resp_file.read_text())
    return e.response_text, e.status_code

@VWS_FLASK_APP.after_request
def set_headers(response: Response) -> Response:
    response.headers['Connection'] = 'keep-alive'
    if response.status_code != codes.INTERNAL_SERVER_ERROR:
        response.headers['Content-Type'] = 'application/json'
    response.headers['Server'] = 'nginx'
    content_length = len(response.data)
    response.headers['Content-Length'] = str(content_length)
    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    response.headers['Date'] = date
    return response


@VWS_FLASK_APP.route('/targets', methods=['POST'])
def add_target() -> Tuple[str, int]:
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

    targets = (target for target in database.targets if not target.delete_date)
    if any(target.name == name for target in targets):
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.TARGET_NAME_EXIST.value,
        }
        return json_dump(body), codes.FORBIDDEN

    active_flag = request_json.get('active_flag')
    if active_flag is None:
        active_flag = True

    image = request_json['image']
    decoded = base64.b64decode(image)
    image_file = io.BytesIO(decoded)

    new_target = Target(
        name=request_json['name'],
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

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.TARGET_CREATED.value,
        'target_id': new_target.target_id,
    }
    return json_dump(body), codes.CREATED


@VWS_FLASK_APP.route('/targets/<string:target_id>', methods=['GET'])
# @JSON_SCHEMA.validate(ADD_TARGET_SCHEMA)
def get_target(target_id: str) -> Tuple[str, int]:
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

    body = {
        'result_code': ResultCodes.SUCCESS.value,
        'transaction_id': uuid.uuid4().hex,
        'target_record': target_record,
        'status': target.status,
    }

    return json_dump(body), codes.OK


@VWS_FLASK_APP.route('/targets/<string:target_id>', methods=['DELETE'])
def delete_target(target_id: str) -> Tuple[str, int]:
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
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.TARGET_STATUS_PROCESSING.value,
        }
        return json_dump(body), codes.FORBIDDEN

    # gmt = pytz.timezone('GMT')
    # now = datetime.datetime.now(tz=gmt)
    # target.delete_date = now
    delete_url = (
        f'{STORAGE_BASE_URL}/databases/{database.database_name}/targets/'
        f'{target_id}'
    )
    requests.delete(url=delete_url)

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.SUCCESS.value,
    }
    return json_dump(body), codes.OK


@VWS_FLASK_APP.route('/summary', methods=['GET'])
def database_summary() -> Tuple[str, int]:
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
        # We have ``self.request_count`` but Vuforia always shows 0.
        # This was not always the case.
        'request_usage': 0,
    }
    return json_dump(body), codes.OK


@VWS_FLASK_APP.route('/duplicates/<string:target_id>', methods=['GET'])
def get_duplicates(target_id: str) -> Tuple[str, int]:
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
        other.target_id for other in other_targets
        if Image.open(other.image) == Image.open(target.image) and
        TargetStatuses.FAILED.value not in (target.status, other.status) and
        TargetStatuses.PROCESSING.value != other.status and other.active_flag
    ]

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.SUCCESS.value,
        'similar_targets': similar_targets,
    }

    return json_dump(body), codes.OK


@VWS_FLASK_APP.route('/targets', methods=['GET'])
def target_list() -> Tuple[str, int]:
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
    results = [
        target.target_id for target in database.targets
        if not target.delete_date
    ]

    body: Dict[str, Union[str, List[str]]] = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.SUCCESS.value,
        'results': results,
    }
    return json_dump(body), codes.OK


# @route(
#     path_pattern=f'/targets/{_TARGET_ID_PATTERN}',
#     http_methods=[PUT],
#     optional_keys={
#         'active_flag',
#         'application_metadata',
#         'image',
#         'name',
#         'width',
#     },
# )
@VWS_FLASK_APP.route('/targets/<string:target_id>', methods=['PUT'])
# TODO
# @JSON_SCHEMA.validate(UPDATE_TARGET_SCHEMA)
def update_target(target_id: str) -> Tuple[str, int]:
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
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.TARGET_STATUS_NOT_SUCCESS.value,
        }
        return json_dump(body), codes.FORBIDDEN

    update_values = {}
    if 'width' in request_json:
        update_values['width'] = request_json['width']

    if 'active_flag' in request_json:
        active_flag = request_json['active_flag']
        if active_flag is None:
            body = {
                'transaction_id': uuid.uuid4().hex,
                'result_code': ResultCodes.FAIL.value,
            }
            return json_dump(body), codes.BAD_REQUEST
        update_values['active_flag'] = active_flag

    if 'application_metadata' in request_json:
        if request_json['application_metadata'] is None:
            body = {
                'transaction_id': uuid.uuid4().hex,
                'result_code': ResultCodes.FAIL.value,
            }
            return json_dump(body), codes.BAD_REQUEST
        application_metadata = request_json['application_metadata']
        update_values['application_metadata'] = application_metadata

    if 'name' in request_json:
        name = request_json['name']
        other_targets = set(database.targets) - set([target])
        if any(
            other.name == name for other in other_targets
            if not other.delete_date
        ):
            body = {
                'transaction_id': uuid.uuid4().hex,
                'result_code': ResultCodes.TARGET_NAME_EXIST.value,
            }
            return json_dump(body), codes.FORBIDDEN
        update_values['name'] = name

    if 'image' in request_json:
        image = request_json['image']
        update_values['image'] = image

    put_url = (
        f'{STORAGE_BASE_URL}/databases/{database.database_name}/targets/'
        f'{target_id}'
    )
    requests.put(url=put_url, json=update_values)

    body = {
        'result_code': ResultCodes.SUCCESS.value,
        'transaction_id': uuid.uuid4().hex,
    }
    return json_dump(body), codes.OK
