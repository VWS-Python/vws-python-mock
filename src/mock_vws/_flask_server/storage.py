"""
Storage layer for the mock Vuforia Flask application.
"""

import base64
import dataclasses
import datetime
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
    target = Target(
        name=request.json['name'],
        width=request.json['width'],
        image_value=image_bytes,
        active_flag=request.json['active_flag'],
        processing_time_seconds=request.json['processing_time_seconds'],
        application_metadata=request.json['application_metadata'],
        target_id=request.json['target_id'],
    )
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
    target = database.get_target(target_id=target_id)
    now = datetime.datetime.now(tz=target.upload_date.tzinfo)
    new_target = dataclasses.replace(target, delete_date=now)
    database.targets.remove(target)
    database.targets.add(new_target)
    return jsonify(new_target.to_dict()), HTTPStatus.OK


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
    target = database.get_target(target_id=target_id)

    width = request.json.get('width', target.width)
    name = request.json.get('name', target.name)
    active_flag = request.json.get('active_flag', target.active_flag)
    application_metadata = request.json.get(
        'application_metadata',
        target.application_metadata,
    )

    image_value = target.image_value
    if 'image' in request.json:
        image_value = base64.b64decode(request.json['image'])

    # In the real implementation, the tracking rating can stay the same.
    # However, for demonstration purposes, the tracking rating changes but
    # when the target is updated.
    available_values = list(set(range(6)) - set([target.tracking_rating]))
    processed_tracking_rating = random.choice(available_values)

    gmt = ZoneInfo('GMT')
    last_modified_date = datetime.datetime.now(tz=gmt)

    new_target = dataclasses.replace(
        target,
        name=name,
        width=width,
        active_flag=active_flag,
        application_metadata=application_metadata,
        image_value=image_value,
        processed_tracking_rating=processed_tracking_rating,
        last_modified_date=last_modified_date,
    )

    database.targets.remove(target)
    database.targets.add(new_target)

    return jsonify(new_target.to_dict()), HTTPStatus.OK


if __name__ == '__main__':  # pragma: no cover
    STORAGE_FLASK_APP.run(debug=True, host='0.0.0.0')
