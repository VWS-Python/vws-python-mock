import base64
import json
import email.utils
import io
import uuid

from flask import Flask, request
from requests import codes

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import json_dump
from mock_vws.target import Target
import wrapt
import uuid
from typing import Any, Callable, Dict, Tuple

import wrapt
from requests import codes
from requests_mock import POST, PUT
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import json_dump

VWS_FLASK_APP = Flask(__name__)

@wrapt.decorator
def validate_content_type_header_given(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate that there is a non-empty content type header given if required.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNAUTHORIZED` response if there is no "Content-Type" header or the
        given header is empty.
    """
    request_needs_content_type = bool(request.method in (POST, PUT))
    if request.headers.get('Content-Type') or not request_needs_content_type:
        return wrapped(*args, **kwargs)

    # context.status_code = codes.UNAUTHORIZED

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.AUTHENTICATION_FAILURE.value,
    }
    return json_dump(body), codes.UNAUTHORIZED

@VWS_FLASK_APP.before_request
@validate_content_type_header_given
def validate_request():
    pass


@VWS_FLASK_APP.after_request
def set_headers(response):
    response.headers['Connection'] = 'keep-alive'
    response.headers['Content-Type'] = 'application/json'
    response.headers['Server'] = 'nginx'
    content_length = len(response.data)
    response.headers['Content-Length'] = str(content_length)
    date = email.utils.formatdate(None, localtime=False, usegmt=True)
    response.headers['Date'] = date
    return response

@VWS_FLASK_APP.route('/targets', methods=['POST'])
def add_target():
    """
    Add a target.

    Fake implementation of
    https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Add-a-Target
    """
    # We do not use ``request.json`` because this only works when the content
    # type is given as ``application/json``.
    request_json = json.loads(request.data)
    name = request_json['name']
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
