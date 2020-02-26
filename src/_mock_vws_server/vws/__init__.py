import base64
import email.utils
import io
import json
import uuid
from typing import Dict, Tuple

import requests
from flask import Flask, Response, request
from flask_json_schema import JsonSchema, JsonValidationError
from requests import codes

from mock_vws._constants import ResultCodes, TargetStatuses
from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._mock_common import json_dump
from mock_vws.database import VuforiaDatabase
from mock_vws.target import Target

from ._constants import STORAGE_BASE_URL
from ._databases import get_all_databases
from ._services_validators import (
    validate_active_flag,
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
from ._services_validators.auth_validators import (
    validate_auth_header_exists,
    validate_auth_header_has_signature,
)
from ._services_validators.content_length_validators import (
    validate_content_length_header_is_int,
    validate_content_length_header_not_too_large,
    validate_content_length_header_not_too_small,
)
from ._services_validators.content_type_validators import (
    validate_content_type_header_given,
)
from ._services_validators.date_validators import (
    validate_date_format,
    validate_date_header_given,
    validate_date_in_range,
)
from ._services_validators.image_validators import (
    validate_image_color_space,
    validate_image_data_type,
    validate_image_encoding,
    validate_image_format,
    validate_image_is_image,
    validate_image_size,
)

VWS_FLASK_APP = Flask(__name__)
JSON_SCHEMA = JsonSchema(VWS_FLASK_APP)

ADD_TARGET_SCHEMA = {
    'required': ['name', 'image', 'width'],
    # TODO are the properties useful for fixing tests?
    'properties': {
        # TODO maybe use more limits on types here and use a max length for string?
        # TODO though actually - if authentication is wrong, surely that's the first issue and then maybe we need to re-think this and not have schema checks - or maybe not until later?
        'name': {
            'type': 'string'
        },
        'image': {},
        'width': {},
        'active_flag': {},
        'application_metadata': {},
    },
    'additionalProperties': False,
}


@VWS_FLASK_APP.before_request
@validate_content_length_header_is_int
@validate_content_length_header_not_too_large
@validate_content_length_header_not_too_small
@validate_auth_header_exists
@validate_auth_header_has_signature
# @validate_access_key_exists
@validate_not_invalid_json
@validate_date_header_given
@validate_date_format
@validate_date_in_range
@validate_content_type_header_given
@validate_width
# TODO is validating the name type needed given JSON schema?
@validate_name_type
@validate_name_length
@validate_name_characters_in_range
@validate_image_data_type
@validate_image_encoding
@validate_image_is_image
@validate_image_format
@validate_image_color_space
@validate_image_size
@validate_active_flag
@validate_metadata_type
@validate_metadata_encoding
@validate_metadata_size
# @validate_authorization
@validate_project_state
def validate_request() -> None:
    pass
    # decorators = [
    #     # parse_target_id,
    #     # update_request_count,
    # ]


@VWS_FLASK_APP.errorhandler(JsonValidationError)
def validation_error(e: JsonValidationError) -> Tuple[str, int]:
    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.FAIL.value,
    }
    return json_dump(body), codes.BAD_REQUEST


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
@JSON_SCHEMA.validate(ADD_TARGET_SCHEMA)
def add_target() -> Tuple[str, int]:
    """
    Add a target.

    Fake implementation of
    https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Add-a-Target
    """
    # We do not use ``request.get_json(force=True)`` because this only works when the content
    # type is given as ``application/json``.
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

    # TODO make this work
    # database.targets.append(new_target)
    # --->
    requests.post(
        url=f'{STORAGE_BASE_URL}/databases/{database.database_name}/targets',
        json=new_target.to_dict(),
    )

    # import pdb; pdb.set_trace()
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
    requests.delete(
        url=
        f'{STORAGE_BASE_URL}/databases/{database.database_name}/targets/{target_id}',
    )

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.SUCCESS.value,
    }
    return json_dump(body), codes.OK
