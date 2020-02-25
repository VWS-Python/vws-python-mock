import base64
import email.utils
import io
import json
import uuid
from typing import Set, Tuple

import requests
from flask import Flask, Response, request
from flask_json_schema import JsonSchema, JsonValidationError
from requests import codes

from mock_vws._constants import ResultCodes
from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._mock_common import json_dump
from mock_vws.database import VuforiaDatabase
from mock_vws.target import Target

from ._services_validators import (
    validate_active_flag,
    validate_metadata_encoding,
    validate_metadata_size,
    validate_metadata_type,
    validate_name_characters_in_range,
    validate_name_length,
    validate_name_type,
    validate_not_invalid_json,
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
# TODO choose something for this - it should actually work in a docker-compose
# scenario.
STORAGE_BASE_URL = 'http://todo.com'

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
# @validate_project_state
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


def get_all_databases() -> Set[VuforiaDatabase]:
    # TODO use the storage URL to get details then cast to VuforiaDatabase
    response = requests.get(url=STORAGE_BASE_URL + '/databases')
    response_json = response.json()
    databases = set()
    for database_dict in response_json:
        database_name = database_dict['database_name']
        server_access_key = database_dict['server_access_key']
        server_secret_key = database_dict['server_secret_key']
        client_access_key = database_dict['client_access_key']
        client_secret_key = database_dict['client_secret_key']
        state = database_dict['state']
        # TODO state

        new_database = VuforiaDatabase(
            database_name=database_name,
            server_access_key=server_access_key,
            server_secret_key=server_secret_key,
            client_access_key=client_access_key,
            client_secret_key=client_secret_key,
            state=state,
        )

        for target_dict in database_dict['targets']:
            # TODO fill this in
            name = target_dict['name']
            active_flag = target_dict['active_flag']
            width= target_dict['width']
            image = target_dict['image']
            processing_time_seconds = target_dict['processing_time_seconds']
            application_metadata = target_dict['application_metadata']

            target = Target(
                name=name,
                active_flag=active_flag,
                width=width,
                image=image,
                processing_time_seconds=processing_time_seconds,
                application_metadata=application_metadata,
            )
            new_database.targets.append(target)

        databases.add(new_database)

    return databases


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

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.TARGET_CREATED.value,
        'target_id': new_target.target_id,
    }
    return json_dump(body), codes.CREATED
