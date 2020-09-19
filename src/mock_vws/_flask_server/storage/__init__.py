"""
Storage layer for the mock Vuforia Flask application.
"""

import base64
import datetime
import io
import random
from http import HTTPStatus
from typing import List, Tuple

from backports.zoneinfo import ZoneInfo
from flask import Flask, jsonify, request

from mock_vws.database import VuforiaDatabase
from mock_vws.states import States
from mock_vws.target import Target

STORAGE_FLASK_APP = Flask(__name__)

VUFORIA_DATABASES: List[VuforiaDatabase] = []


@STORAGE_FLASK_APP.route('/reset', methods=['POST'])
def reset() -> Tuple[str, int]:
    """
    Reset the back-end to a state of no databases.
    """
    VUFORIA_DATABASES.clear()
    return '', HTTPStatus.OK


@STORAGE_FLASK_APP.route('/databases', methods=['GET'])
def get_databases() -> Tuple[str, int]:
    """
    Return a list of all databases.
    """
    databases = [database.to_dict() for database in VUFORIA_DATABASES]
    return jsonify(databases), HTTPStatus.OK


@STORAGE_FLASK_APP.route('/databases', methods=['POST'])
def create_database() -> Tuple[str, int]:
    """
    Create a new database.
    """
    server_access_key = request.json['server_access_key']
    server_secret_key = request.json['server_secret_key']
    client_access_key = request.json['client_access_key']
    client_secret_key = request.json['client_secret_key']
    database_name = request.json['database_name']
    state = States[request.json['state_name']]

    database = VuforiaDatabase(
        server_access_key=server_access_key,
        server_secret_key=server_secret_key,
        client_access_key=client_access_key,
        client_secret_key=client_secret_key,
        database_name=database_name,
        state=state,
    )
    VUFORIA_DATABASES.append(database)
    return jsonify(database.to_dict()), HTTPStatus.CREATED


@STORAGE_FLASK_APP.route(
    '/databases/<string:database_name>/targets',
    methods=['POST'],
)
def create_target(database_name: str) -> Tuple[str, int]:
    """
    Create a new target in a given database.
    """
    [database] = [
        database
        for database in VUFORIA_DATABASES
        if database.database_name == database_name
    ]
    image_base64 = request.json['image_base64']
    image_bytes = base64.b64decode(image_base64)
    image = io.BytesIO(image_bytes)
    target = Target(
        name=request.json['name'],
        width=request.json['width'],
        image=image,
        active_flag=request.json['active_flag'],
        processing_time_seconds=request.json['processing_time_seconds'],
        application_metadata=request.json['application_metadata'],
    )
    target.target_id = request.json['target_id']
    database.targets.add(target)

    return jsonify(target.to_dict()), HTTPStatus.CREATED


@STORAGE_FLASK_APP.route(
    '/databases/<string:database_name>/targets/<string:target_id>',
    methods=['DELETE'],
)
def delete_target(database_name: str, target_id: str) -> Tuple[str, int]:
    """
    Delete a target.
    """
    [database] = [
        database
        for database in VUFORIA_DATABASES
        if database.database_name == database_name
    ]
    [target] = [
        target for target in database.targets if target.target_id == target_id
    ]
    target.delete()
    return jsonify(target.to_dict()), HTTPStatus.OK


@STORAGE_FLASK_APP.route(
    '/databases/<string:database_name>/targets/<string:target_id>',
    methods=['PUT'],
)
def update_target(database_name: str, target_id: str) -> Tuple[str, int]:
    """
    Update a target.
    """
    [database] = [
        database
        for database in VUFORIA_DATABASES
        if database.database_name == database_name
    ]
    [target] = [
        target for target in database.targets if target.target_id == target_id
    ]

    if 'name' in request.json:
        target.name = request.json['name']

    if 'active_flag' in request.json:
        target.active_flag = bool(request.json['active_flag'])

    if 'width' in request.json:
        target.width = float(request.json['width'])

    if 'application_metadata' in request.json:
        target.application_metadata = request.json['application_metadata']

    if 'image' in request.json:
        decoded = base64.b64decode(request.json['image'])
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

    return jsonify(target.to_dict()), HTTPStatus.OK
