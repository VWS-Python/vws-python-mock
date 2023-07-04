"""
Storage layer for the mock Vuforia Flask application.
"""

import base64
import dataclasses
import datetime
import json
from enum import StrEnum, auto
from http import HTTPStatus
from zoneinfo import ZoneInfo

from flask import Flask, Response, request
from pydantic_settings import BaseSettings

from mock_vws.database import VuforiaDatabase
from mock_vws.states import States
from mock_vws.target import Target
from mock_vws.target_manager import TargetManager
from mock_vws.target_raters import (
    BrisqueTargetTrackingRater,
    HardcodedTargetTrackingRater,
    RandomTargetTrackingRater,
    TargetTrackingRater,
)

TARGET_MANAGER_FLASK_APP = Flask(__name__)

TARGET_MANAGER = TargetManager()


class _TargetRaterChoice(StrEnum):
    """Target rater choices."""

    BRISQUE = auto()
    PERFECT = auto()
    RANDOM = auto()

    def to_target_rater(self) -> TargetTrackingRater:
        """Get the target rater."""
        rater = {
            _TargetRaterChoice.BRISQUE: BrisqueTargetTrackingRater(),
            _TargetRaterChoice.PERFECT: HardcodedTargetTrackingRater(rating=5),
            _TargetRaterChoice.RANDOM: RandomTargetTrackingRater(),
        }[self]
        assert isinstance(rater, TargetTrackingRater)
        return rater


class TargetManagerSettings(BaseSettings):
    """Settings for the Target Manager Flask app."""

    target_manager_host: str = ""
    target_rater: _TargetRaterChoice = _TargetRaterChoice.BRISQUE


@TARGET_MANAGER_FLASK_APP.route(
    "/databases/<string:database_name>",
    methods=["DELETE"],
)
def delete_database(database_name: str) -> Response:
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
        return Response(response="", status=HTTPStatus.NOT_FOUND)

    TARGET_MANAGER.remove_database(database=matching_database)
    return Response(response="", status=HTTPStatus.OK)


@TARGET_MANAGER_FLASK_APP.route("/databases", methods=["GET"])
def get_databases() -> Response:
    """
    Return a list of all databases.
    """
    databases = [database.to_dict() for database in TARGET_MANAGER.databases]
    return Response(
        response=json.dumps(obj=databases),
        status=HTTPStatus.OK,
    )


@TARGET_MANAGER_FLASK_APP.route("/databases", methods=["POST"])
def create_database() -> Response:
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
    request_json = json.loads(request.data)
    server_access_key = request_json.get(
        "server_access_key",
        random_database.server_access_key,
    )
    server_secret_key = request_json.get(
        "server_secret_key",
        random_database.server_secret_key,
    )
    client_access_key = request_json.get(
        "client_access_key",
        random_database.client_access_key,
    )
    client_secret_key = request_json.get(
        "client_secret_key",
        random_database.client_secret_key,
    )
    database_name = request_json.get(
        "database_name",
        random_database.database_name,
    )
    state_name = request_json.get(
        "state_name",
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
        return Response(
            response=str(exc),
            status=HTTPStatus.CONFLICT,
        )

    return Response(
        response=json.dumps(database.to_dict()),
        status=HTTPStatus.CREATED,
    )


@TARGET_MANAGER_FLASK_APP.route(
    "/databases/<string:database_name>/targets",
    methods=["POST"],
)
def create_target(database_name: str) -> Response:
    """
    Create a new target in a given database.
    """
    (database,) = (
        database
        for database in TARGET_MANAGER.databases
        if database.database_name == database_name
    )
    request_json = json.loads(request.data)
    image_base64 = request_json["image_base64"]
    image_bytes = base64.b64decode(s=image_base64)
    settings = TargetManagerSettings.model_validate(obj={})
    target_tracking_rater = settings.target_rater.to_target_rater()

    target = Target(
        name=request_json["name"],
        width=request_json["width"],
        image_value=image_bytes,
        active_flag=request_json["active_flag"],
        processing_time_seconds=request_json["processing_time_seconds"],
        application_metadata=request_json["application_metadata"],
        target_id=request_json["target_id"],
        target_tracking_rater=target_tracking_rater,
    )
    database.targets.add(target)

    return Response(
        response=json.dumps(target.to_dict()),
        status=HTTPStatus.CREATED,
    )


@TARGET_MANAGER_FLASK_APP.route(
    "/databases/<string:database_name>/targets/<string:target_id>",
    methods=["DELETE"],
)
def delete_target(database_name: str, target_id: str) -> Response:
    """
    Delete a target.
    """
    (database,) = (
        database
        for database in TARGET_MANAGER.databases
        if database.database_name == database_name
    )
    target = database.get_target(target_id=target_id)
    now = datetime.datetime.now(tz=target.upload_date.tzinfo)
    new_target = dataclasses.replace(target, delete_date=now)
    database.targets.remove(target)
    database.targets.add(new_target)
    return Response(
        response=json.dumps(new_target.to_dict()),
        status=HTTPStatus.OK,
    )


@TARGET_MANAGER_FLASK_APP.route(
    "/databases/<string:database_name>/targets/<string:target_id>",
    methods=["PUT"],
)
def update_target(database_name: str, target_id: str) -> Response:
    """
    Update a target.
    """
    (database,) = (
        database
        for database in TARGET_MANAGER.databases
        if database.database_name == database_name
    )
    target = database.get_target(target_id=target_id)

    request_json = json.loads(request.data)
    width = request_json.get("width", target.width)
    name = request_json.get("name", target.name)
    active_flag = request_json.get("active_flag", target.active_flag)
    application_metadata = request_json.get(
        "application_metadata",
        target.application_metadata,
    )

    image_value = target.image_value
    request_json = json.loads(request.data)
    if "image" in request_json:
        image_value = base64.b64decode(s=request_json["image"])

    gmt = ZoneInfo("GMT")
    last_modified_date = datetime.datetime.now(tz=gmt)

    new_target = dataclasses.replace(
        target,
        name=name,
        width=width,
        active_flag=active_flag,
        application_metadata=application_metadata,
        image_value=image_value,
        last_modified_date=last_modified_date,
    )

    database.targets.remove(target)
    database.targets.add(new_target)

    return Response(
        response=json.dumps(new_target.to_dict()),
        status=HTTPStatus.OK,
    )


if __name__ == "__main__":  # pragma: no cover
    SETTINGS = TargetManagerSettings.model_validate(obj={})
    TARGET_MANAGER_FLASK_APP.run(host=SETTINGS.target_manager_host)
