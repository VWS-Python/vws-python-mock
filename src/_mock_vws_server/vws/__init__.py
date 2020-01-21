import base64
import io
import uuid

from flask import Flask, request
from requests import codes

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import json_dump
from mock_vws.target import Target

VWS_FLASK_APP = Flask(__name__)


@VWS_FLASK_APP.route('/targets', methods=['POST'])
def _():
    """
    Add a target.

    Fake implementation of
    https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Add-a-Target
    """
    request.json['name']
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

    active_flag = request.json.get('active_flag')
    if active_flag is None:
        active_flag = True

    image = request.json['image']
    decoded = base64.b64decode(image)
    image_file = io.BytesIO(decoded)

    new_target = Target(
        name=request.json['name'],
        width=request.json['width'],
        image=image_file,
        active_flag=active_flag,
        processing_time_seconds=0.2,
        # processing_time_seconds=self._processing_time_seconds,
        application_metadata=request.json.get('application_metadata'),
    )
    # database.targets.append(new_target)

    # context.status_code = codes.CREATED
    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.TARGET_CREATED.value,
        'target_id': new_target.target_id,
    }
    return json_dump(body), codes.CREATED
