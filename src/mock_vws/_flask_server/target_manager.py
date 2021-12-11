"""
Storage layer for the mock Vuforia Flask application.
"""

import base64
import dataclasses
import datetime
import random
from http import HTTPStatus
from typing import Tuple
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request

from mock_vws.database import VuforiaDatabase
from mock_vws.states import States
from mock_vws.target import Target
from mock_vws.target_manager import TargetManager

TARGET_MANAGER_FLASK_APP = Flask(__name__)

TARGET_MANAGER = TargetManager()


@TARGET_MANAGER_FLASK_APP.route(
    '/databases/<string:database_name>',
    methods=['DELETE'],
)
def delete_database(database_name: str) -> Tuple[str, int]:
    """
    Delete a database.

    :status 200: The database has been deleted.
    """
    try:
        (matching_database,) = {
            database
            for database in TARGET_MANAGER.databases
            if database_name == database.database_name
        }
    except ValueError:
        return '', HTTPStatus.NOT_FOUND

    TARGET_MANAGER.remove_database(database=matching_database)
    return '', HTTPStatus.OK


@TARGET_MANAGER_FLASK_APP.route('/databases', methods=['GET'])
def get_databases() -> Tuple[str, int]:
    """
    Return a list of all databases.
    """
    databases = [database.to_dict() for database in TARGET_MANAGER.databases]
    return jsonify(databases), HTTPStatus.OK


@TARGET_MANAGER_FLASK_APP.route('/databases', methods=['POST'])
def create_database() -> Tuple[str, int]:
    """
    Create a new database.

    :reqheader Content-Type: application/json
    :resheader Content-Type: application/json

    :reqjson string client_access_key: (Optional) The client access key for the
      database.
    :reqjson string client_secret_key: (Optional) The client secret key for the
      database.
    :reqjson string database_name: (Optional) The name of the database.
    :reqjson string server_access_key: (Optional) The server access key for the
      database.
    :reqjson string server_secret_key: (Optional) The server secret key for the
      database.
    :reqjson string state_name: (Optional) The state of the database. This can
     be "WORKING" or "PROJECT_INACTIVE". This defaults to "WORKING".

    :resjson string client_access_key: The client access key for the database.
    :resjson string client_secret_key: The client secret key for the database.
    :resjson string database_name: The database name.
    :resjson string server_access_key: The server access key for the database.
    :resjson string server_secret_key: The server secret key for the database.
    :resjson string state_name: The database state. This will be "WORKING" or
      "PROJECT_INACTIVE".
    :reqjsonarr targets: The targets in the database.

    :status 201: The database has been successfully created.
    """
    random_database = VuforiaDatabase()
    server_access_key = request.json.get(
        'server_access_key',
        random_database.server_access_key,
    )
    server_secret_key = request.json.get(
        'server_secret_key',
        random_database.server_secret_key,
    )
    client_access_key = request.json.get(
        'client_access_key',
        random_database.client_access_key,
    )
    client_secret_key = request.json.get(
        'client_secret_key',
        random_database.client_secret_key,
    )
    database_name = request.json.get(
        'database_name',
        random_database.database_name,
    )
    state_name = request.json.get(
        'state_name',
        random_database.state.name,
    )

    state = States[state_name]

    database = VuforiaDatabase(
        server_access_key=server_access_key,
        server_secret_key=server_secret_key,
        client_access_key=client_access_key,
        client_secret_key=client_secret_key,
        database_name=database_name,
        state=state,
    )
    try:
        TARGET_MANAGER.add_database(database=database)
    except ValueError as exc:
        return str(exc), HTTPStatus.CONFLICT

    return jsonify(database.to_dict()), HTTPStatus.CREATED


@TARGET_MANAGER_FLASK_APP.route(
    '/databases/<string:database_name>/targets',
    methods=['POST'],
)
def create_target(database_name: str) -> Tuple[str, int]:
    """
    Create a new target in a given database.
    """
    [database] = [
        database
        for database in TARGET_MANAGER.databases
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


@TARGET_MANAGER_FLASK_APP.route(
    '/databases/<string:database_name>/targets/<string:target_id>',
    methods=['DELETE'],
)
def delete_target(database_name: str, target_id: str) -> Tuple[str, int]:
    """
    Delete a target.
    """
    [database] = [
        database
        for database in TARGET_MANAGER.databases
        if database.database_name == database_name
    ]
    target = database.get_target(target_id=target_id)
    now = datetime.datetime.now(tz=target.upload_date.tzinfo)
    new_target = dataclasses.replace(target, delete_date=now)
    database.targets.remove(target)
    database.targets.add(new_target)
    return jsonify(new_target.to_dict()), HTTPStatus.OK


@TARGET_MANAGER_FLASK_APP.route(
    '/databases/<string:database_name>/targets/<string:target_id>',
    methods=['PUT'],
)
def update_target(database_name: str, target_id: str) -> Tuple[str, int]:
    """
    Update a target.
    """
    [database] = [
        database
        for database in TARGET_MANAGER.databases
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
    available_values = list(set(range(6)) - {target.tracking_rating})
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
    TARGET_MANAGER_FLASK_APP.run(debug=True, host='0.0.0.0')
