import base64
import email.utils
import io
import json
import uuid

from flask import Flask, request, session
from requests import codes
from flask_json_schema import JsonSchema, JsonValidationError

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import json_dump
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
    validate_access_key_exists,
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
        'name': { 'type': 'string' },
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
def validate_request():
    pass
    # decorators = [
    #     # parse_target_id,
    #     # update_request_count,
    # ]

@VWS_FLASK_APP.errorhandler(JsonValidationError)
def validation_error(e):
    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.FAIL.value,
    }
    return json_dump(body), codes.BAD_REQUEST



@VWS_FLASK_APP.after_request
def set_headers(response):
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
def add_target():
    """
    Add a target.

    Fake implementation of
    https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Add-a-Target
    """
    # We do not use ``request.get_json(force=True)`` because this only works when the content
    # type is given as ``application/json``.
    request_json = json.loads(request.data)
    request_json['name']
    # database = get_database_matching_server_keys(
    #     request=request,
    #     databases=self.databases,
    # )
    #
    # assert isinstance(database, VuforiaDatabase)
    #
    # (target for target in database.targets if not target.delete_date)
    # if any(target.name == name for target in targets):
    #     context.status_code = codes.FORBIDDEN
    #     body = {
    #         'transaction_id': uuid.uuid4().hex,
    #         'result_code': ResultCodes.TARGET_NAME_EXIST.value,
    #     }
    #     return json_dump(body)

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
    # database.targets.append(new_target)

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.TARGET_CREATED.value,
        'target_id': new_target.target_id,
    }
    return json_dump(body), codes.CREATED
