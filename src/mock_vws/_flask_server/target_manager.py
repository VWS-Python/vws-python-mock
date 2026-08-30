"""Storage layer for the mock Vuforia Flask application."""

import base64
import copy
import datetime
import json
from enum import StrEnum, auto
from http import HTTPMethod, HTTPStatus
from typing import assert_never
from zoneinfo import ZoneInfo

from beartype import beartype
from flask import Flask, Response, request
from pydantic_settings import BaseSettings

from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.database_type import DatabaseType
from mock_vws.model_target import ModelTargetDataset, OAuth2ClientCredential
from mock_vws.request_rate_limits import RequestRateLimits
from mock_vws.states import States
from mock_vws.target import ImageTarget, VuMarkTarget
from mock_vws.target_manager import TargetManager
from mock_vws.target_raters import (
    BrisqueTargetTrackingRater,
    HardcodedTargetTrackingRater,
    RandomTargetTrackingRater,
    TargetTrackingRater,
)

TARGET_MANAGER_FLASK_APP = Flask(import_name=__name__, static_folder=None)

TARGET_MANAGER = TargetManager()


@beartype
class _TargetRaterChoice(StrEnum):
    """Target rater choices."""

    BRISQUE = auto()
    PERFECT = auto()
    RANDOM = auto()

    def to_target_rater(
        self: _TargetRaterChoice,
    ) -> TargetTrackingRater:
        """Get the target rater."""
        match self:
            case _TargetRaterChoice.BRISQUE:
                return BrisqueTargetTrackingRater()
            case _TargetRaterChoice.PERFECT:
                return HardcodedTargetTrackingRater(rating=5)
            case _TargetRaterChoice.RANDOM:
                return RandomTargetTrackingRater()
            case _ as unreachable:
                assert_never(unreachable)


@beartype
class TargetManagerSettings(BaseSettings):
    """Settings for the Target Manager Flask app."""

    target_manager_host: str = ""
    target_rater: _TargetRaterChoice = _TargetRaterChoice.BRISQUE


@TARGET_MANAGER_FLASK_APP.route(
    rule="/cloud_databases/<string:database_name>",
    methods=[HTTPMethod.DELETE],
)
@beartype
def delete_cloud_database(database_name: str) -> Response:
    """Delete a cloud database.

    :status 200: The cloud database has been deleted.
    """
    with TARGET_MANAGER.lock:
        try:
            (matching_database,) = {
                database
                for database in TARGET_MANAGER.cloud_databases
                if database_name == database.database_name
            }
        except ValueError:
            return Response(response="", status=HTTPStatus.NOT_FOUND)

        TARGET_MANAGER.remove_cloud_database(cloud_database=matching_database)

    return Response(response="", status=HTTPStatus.OK)


@TARGET_MANAGER_FLASK_APP.route(
    rule="/vumark_databases/<string:database_name>",
    methods=[HTTPMethod.DELETE],
)
@beartype
def delete_vumark_database(database_name: str) -> Response:
    """Delete a VuMark database.

    :status 200: The VuMark database has been deleted.
    """
    with TARGET_MANAGER.lock:
        try:
            (matching_database,) = {
                database
                for database in TARGET_MANAGER.vumark_databases
                if database_name == database.database_name
            }
        except ValueError:
            return Response(response="", status=HTTPStatus.NOT_FOUND)

        TARGET_MANAGER.remove_vumark_database(
            vumark_database=matching_database,
        )

    return Response(response="", status=HTTPStatus.OK)


@TARGET_MANAGER_FLASK_APP.route(
    rule="/cloud_databases", methods=[HTTPMethod.GET]
)
@beartype
def get_cloud_databases() -> Response:
    """Return a list of all cloud databases."""
    with TARGET_MANAGER.lock:
        databases = [
            database.to_dict() for database in TARGET_MANAGER.cloud_databases
        ]

    return Response(
        response=json.dumps(obj=databases),
        status=HTTPStatus.OK,
    )


@TARGET_MANAGER_FLASK_APP.route(
    rule="/vumark_databases",
    methods=[HTTPMethod.GET],
)
@beartype
def get_vumark_databases() -> Response:
    """Return a list of all VuMark databases."""
    with TARGET_MANAGER.lock:
        databases = [
            database.to_dict() for database in TARGET_MANAGER.vumark_databases
        ]

    return Response(
        response=json.dumps(obj=databases),
        status=HTTPStatus.OK,
    )


@TARGET_MANAGER_FLASK_APP.route(
    rule="/cloud_databases", methods=[HTTPMethod.POST]
)
@beartype
def create_cloud_database() -> Response:
    """Create a new cloud database.

    :reqheader Content-Type: application/json
    :resheader Content-Type: application/json

    :reqjson string client_access_key: (Optional) The client access key for the
      cloud database.

    :reqjson string client_secret_key: (Optional) The client secret key for the
      cloud database.

    :reqjson string database_name: (Optional) The name of the cloud database.

    :reqjson int request_quota: (Optional) The request quota. Set this to zero
      to make VWS endpoints return ``RequestQuotaReached``.

    :reqjson int target_quota: (Optional) The target quota. Once this many
      targets exist, adding another returns ``TargetQuotaReached``.

    :reqjson int reco_threshold: (Optional) The recognition threshold shown in
      the database summary report.

    :reqjson int current_month_recos: (Optional) The number of recognitions in
      the current month, shown in the database summary report.

    :reqjson int previous_month_recos: (Optional) The number of recognitions in
      the previous month, shown in the database summary report.

    :reqjson int total_recos: (Optional) The total number of recognitions,
      shown in the database summary report.

    :reqjson int requests_per_second_limit: (Optional) The maximum number of
      VWS requests accepted in a rolling one-second window, across all VWS
      endpoints. Set this to zero to make VWS endpoints return
      ``TooManyRequests``.

    :reqjson request_rate_limits: (Optional) Request rate limits for
      individual groups of VWS endpoints. This is an object with the optional
      keys "other", "get_target", "get_duplicates" and "list_targets", each
      either null or an object with the keys "max_requests" and
      "window_seconds".

    :reqjson string server_access_key: (Optional) The server access key for the
      cloud database.

    :reqjson string server_secret_key: (Optional) The server secret key for the
      cloud database.

    :reqjson string state_name: (Optional) The state of the cloud database.
     This can be "WORKING", "PROJECT_INACTIVE", "PROJECT_SUSPENDED", or
     "PROJECT_HAS_NO_API_ACCESS". This defaults to "WORKING".

    :resjson string client_access_key: The client access key for the cloud
      database.

    :resjson string client_secret_key: The client secret key for the cloud
      database.

    :resjson string database_name: The cloud database name.

    :resjson int request_quota: The request quota.

    :resjson int target_quota: The target quota.

    :resjson int requests_per_second_limit: The per-second request limit, or
      null when rate limiting is disabled.

    :resjson request_rate_limits: The per-endpoint request rate limits, or
      null when per-endpoint rate limiting is disabled.

    :resjson string server_access_key: The server access key for the cloud
      database.

    :resjson string server_secret_key: The server secret key for the cloud
      database.

    :resjson string state_name: The cloud database state.

    :reqjsonarr targets: The targets in the cloud database.

    :status 201: The cloud database has been successfully created.
    """
    random_database = CloudDatabase()
    request_json = json.loads(s=request.data)
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
    database_id = request_json.get(
        "database_id",
        random_database.database_id,
    )
    database_name = request_json.get(
        "database_name",
        random_database.database_name,
    )
    state_name = request_json.get(
        "state_name",
        random_database.state.name,
    )
    database_type_name = request_json.get(
        "database_type_name",
        random_database.database_type.name,
    )
    request_quota = request_json.get(
        "request_quota",
        random_database.request_quota,
    )
    target_quota = request_json.get(
        "target_quota",
        random_database.target_quota,
    )
    reco_threshold = request_json.get(
        "reco_threshold",
        random_database.reco_threshold,
    )
    current_month_recos = request_json.get(
        "current_month_recos",
        random_database.current_month_recos,
    )
    previous_month_recos = request_json.get(
        "previous_month_recos",
        random_database.previous_month_recos,
    )
    total_recos = request_json.get(
        "total_recos",
        random_database.total_recos,
    )
    requests_per_second_limit = request_json.get(
        "requests_per_second_limit",
        random_database.requests_per_second_limit,
    )
    request_rate_limits_dict = request_json.get("request_rate_limits")
    request_rate_limits = (
        None
        if request_rate_limits_dict is None
        else RequestRateLimits.from_dict(limits_dict=request_rate_limits_dict)
    )

    state = States[state_name]
    database_type = DatabaseType[database_type_name]

    database = CloudDatabase(
        server_access_key=server_access_key,
        server_secret_key=server_secret_key,
        client_access_key=client_access_key,
        client_secret_key=client_secret_key,
        database_id=database_id,
        database_name=database_name,
        state=state,
        database_type=database_type,
        request_quota=request_quota,
        target_quota=target_quota,
        reco_threshold=reco_threshold,
        current_month_recos=current_month_recos,
        previous_month_recos=previous_month_recos,
        total_recos=total_recos,
        requests_per_second_limit=requests_per_second_limit,
        request_rate_limits=request_rate_limits,
    )
    with TARGET_MANAGER.lock:
        try:
            TARGET_MANAGER.add_cloud_database(cloud_database=database)
        except ValueError as exc:
            return Response(
                response=str(object=exc),
                status=HTTPStatus.CONFLICT,
            )

        database_dict = database.to_dict()

    return Response(
        response=json.dumps(obj=database_dict),
        status=HTTPStatus.CREATED,
    )


@TARGET_MANAGER_FLASK_APP.route(
    rule="/vumark_databases",
    methods=[HTTPMethod.POST],
)
@beartype
def create_vumark_database() -> Response:
    """Create a new VuMark database.

    :status 201: The database has been successfully created.
    """
    request_json = json.loads(s=request.data)
    random_vumark_database = VuMarkDatabase()
    state_name = request_json.get(
        "state_name",
        random_vumark_database.state.name,
    )
    database = VuMarkDatabase(
        server_access_key=request_json.get(
            "server_access_key",
            random_vumark_database.server_access_key,
        ),
        server_secret_key=request_json.get(
            "server_secret_key",
            random_vumark_database.server_secret_key,
        ),
        database_name=request_json.get(
            "database_name",
            random_vumark_database.database_name,
        ),
        state=States[state_name],
    )

    with TARGET_MANAGER.lock:
        try:
            TARGET_MANAGER.add_vumark_database(vumark_database=database)
        except ValueError as exc:
            return Response(
                response=str(object=exc),
                status=HTTPStatus.CONFLICT,
            )

        database_dict = database.to_dict()

    return Response(
        response=json.dumps(obj=database_dict),
        status=HTTPStatus.CREATED,
    )


@TARGET_MANAGER_FLASK_APP.route(
    rule="/model_target_datasets",
    methods=[HTTPMethod.GET],
)
@beartype
def get_model_target_datasets() -> Response:
    """Return a list of all Model Target datasets."""
    datasets = [
        dataset.to_dict()
        for dataset in TARGET_MANAGER.model_target_datasets.values()
    ]
    return Response(
        response=json.dumps(obj=datasets),
        status=HTTPStatus.OK,
    )


@TARGET_MANAGER_FLASK_APP.route(
    rule="/model_target_datasets",
    methods=[HTTPMethod.POST],
)
@beartype
def create_model_target_dataset() -> Response:
    """Create a new Model Target dataset.

    :status 201: The Model Target dataset has been successfully created.
    """
    request_json = json.loads(s=request.data)
    dataset = ModelTargetDataset.from_dict(dataset_dict=request_json)
    TARGET_MANAGER.add_model_target_dataset(model_target_dataset=dataset)
    return Response(
        response=json.dumps(obj=dataset.to_dict()),
        status=HTTPStatus.CREATED,
    )


@TARGET_MANAGER_FLASK_APP.route(
    rule="/model_target_datasets/<string:dataset_uuid>",
    methods=[HTTPMethod.DELETE],
)
@beartype
def delete_model_target_dataset(dataset_uuid: str) -> Response:
    """Delete a Model Target dataset.

    :status 200: The Model Target dataset has been deleted.
    """
    with TARGET_MANAGER.lock:
        if dataset_uuid not in TARGET_MANAGER.model_target_datasets:
            return Response(response="", status=HTTPStatus.NOT_FOUND)

        TARGET_MANAGER.remove_model_target_dataset(dataset_uuid=dataset_uuid)

    return Response(response="", status=HTTPStatus.OK)


@TARGET_MANAGER_FLASK_APP.route(
    rule="/oauth2_client_credentials",
    methods=[HTTPMethod.GET],
)
@beartype
def get_oauth2_client_credentials() -> Response:
    """Return all OAuth2 client credentials."""
    credentials = [
        {
            "client_id": credential.client_id,
            "client_secret": credential.client_secret,
            "scopes": list(credential.scopes),
        }
        for credential in TARGET_MANAGER.oauth2_client_credentials.values()
    ]
    return Response(
        response=json.dumps(obj=credentials),
        status=HTTPStatus.OK,
    )


@TARGET_MANAGER_FLASK_APP.route(
    rule="/oauth2_client_credentials",
    methods=[HTTPMethod.POST],
)
@beartype
def put_oauth2_client_credential() -> Response:
    """Add or replace an OAuth2 client credential."""
    value = json.loads(s=request.data)
    credential = OAuth2ClientCredential(
        client_id=value["client_id"],
        client_secret=value["client_secret"],
        scopes=tuple(value["scopes"]),
    )
    TARGET_MANAGER.add_oauth2_client_credential(credential=credential)
    return Response(response="", status=HTTPStatus.NO_CONTENT)


@TARGET_MANAGER_FLASK_APP.route(
    rule="/oauth2_client_credentials/<string:client_id>",
    methods=[HTTPMethod.DELETE],
)
@beartype
def remove_oauth2_client_credential(client_id: str) -> Response:
    """Remove an OAuth2 client credential."""
    if client_id not in TARGET_MANAGER.oauth2_client_credentials:
        return Response(response="", status=HTTPStatus.NOT_FOUND)
    TARGET_MANAGER.remove_oauth2_client_credential(client_id=client_id)
    return Response(response="", status=HTTPStatus.NO_CONTENT)


@TARGET_MANAGER_FLASK_APP.route(
    rule="/cloud_databases/<string:database_name>/targets",
    methods=[HTTPMethod.POST],
)
@beartype
def create_target(database_name: str) -> Response:
    """Create a new target in a given cloud database."""
    request_json = json.loads(s=request.data)
    settings = TargetManagerSettings.model_validate(obj={})

    image_bytes = base64.b64decode(s=request_json["image_base64"])
    target_tracking_rater = settings.target_rater.to_target_rater()
    target = ImageTarget(
        name=request_json["name"],
        width=request_json["width"],
        image_value=image_bytes,
        active_flag=request_json["active_flag"],
        processing_time_seconds=request_json["processing_time_seconds"],
        application_metadata=request_json["application_metadata"],
        target_id=request_json["target_id"],
        target_tracking_rater=target_tracking_rater,
    )
    with TARGET_MANAGER.lock:
        (database,) = (
            database
            for database in TARGET_MANAGER.cloud_databases
            if database.database_name == database_name
        )
        database.targets.add(target)

    return Response(
        response=json.dumps(obj=target.to_dict()),
        status=HTTPStatus.CREATED,
    )


@TARGET_MANAGER_FLASK_APP.route(
    rule="/vumark_databases/<string:database_name>/vumark_targets",
    methods=[HTTPMethod.POST],
)
@beartype
def create_vumark_target(database_name: str) -> Response:
    """Create a new VuMark target in a given database."""
    request_json = json.loads(s=request.data)
    target = VuMarkTarget.from_dict(target_dict=request_json)
    with TARGET_MANAGER.lock:
        (database,) = (
            database
            for database in TARGET_MANAGER.vumark_databases
            if database.database_name == database_name
        )
        database.vumark_targets.add(target)

    return Response(
        response=json.dumps(obj=target.to_dict()),
        status=HTTPStatus.CREATED,
    )


@TARGET_MANAGER_FLASK_APP.route(
    rule="/cloud_databases/<string:database_name>/targets/<string:target_id>",
    methods={HTTPMethod.DELETE},
)
@beartype
def delete_target(database_name: str, target_id: str) -> Response:
    """Delete a target."""
    with TARGET_MANAGER.lock:
        (database,) = (
            database
            for database in TARGET_MANAGER.cloud_databases
            if database.database_name == database_name
        )
        target = database.get_target(target_id=target_id)
        now = datetime.datetime.now(tz=target.upload_date.tzinfo)
        # See https://github.com/facebook/pyrefly/issues/1897
        new_target: ImageTarget = copy.replace(
            target,  # pyrefly: ignore[bad-argument-type]
            delete_date=now,
        )
        database.targets.remove(target)
        database.targets.add(new_target)

    return Response(
        response=json.dumps(obj=new_target.to_dict()),
        status=HTTPStatus.OK,
    )


@TARGET_MANAGER_FLASK_APP.route(
    rule="/cloud_databases/<string:database_name>/targets/<string:target_id>",
    methods=[HTTPMethod.PUT],
)
@beartype
def update_target(database_name: str, target_id: str) -> Response:
    """Update a target."""
    request_json = json.loads(s=request.data)

    with TARGET_MANAGER.lock:
        (database,) = (
            database
            for database in TARGET_MANAGER.cloud_databases
            if database.database_name == database_name
        )
        target = database.get_target(target_id=target_id)

        name = request_json.get("name", target.name)
        active_flag = request_json.get("active_flag", target.active_flag)

        gmt = ZoneInfo(key="GMT")
        last_modified_date = datetime.datetime.now(tz=gmt)

        width = request_json.get("width", target.width)
        application_metadata = request_json.get(
            "application_metadata",
            target.application_metadata,
        )
        image_value = target.image_value
        if "image" in request_json:
            image_value = base64.b64decode(s=request_json["image"])
        # See https://github.com/facebook/pyrefly/issues/1897
        new_target: ImageTarget = copy.replace(
            target,  # pyrefly: ignore[bad-argument-type]
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
        response=json.dumps(obj=new_target.to_dict()),
        status=HTTPStatus.OK,
    )


@TARGET_MANAGER_FLASK_APP.route(
    rule=(
        "/cloud_databases/<string:database_name>/targets/<string:target_id>"
        "/recognition_counts"
    ),
    methods=[HTTPMethod.POST],
)
@beartype
def set_target_recognition_counts(
    database_name: str,
    target_id: str,
) -> Response:
    """Set the recognition counts of a target.

    A recognition is not a change to the target, so unlike a target update
    this does not change the target's last modified date, and a processed
    target does not go back to being processed.

    :reqjson int current_month_recos: (Optional) The number of recognitions of
      this target in the current month. If not given, the count is left as it
      is.

    :reqjson int previous_month_recos: (Optional) The number of recognitions of
      this target in the previous month. If not given, the count is left as it
      is.

    :reqjson int total_recos: (Optional) The total number of recognitions of
      this target. If not given, the count is left as it is.

    :status 200: The recognition counts have been set.
    """
    request_json = json.loads(s=request.data)

    with TARGET_MANAGER.lock:
        (database,) = (
            database
            for database in TARGET_MANAGER.cloud_databases
            if database.database_name == database_name
        )
        target = database.get_target(target_id=target_id)

        # See https://github.com/facebook/pyrefly/issues/1897
        new_target: ImageTarget = copy.replace(
            target,  # pyrefly: ignore[bad-argument-type]
            current_month_recos=request_json.get(
                "current_month_recos",
                target.current_month_recos,
            ),
            previous_month_recos=request_json.get(
                "previous_month_recos",
                target.previous_month_recos,
            ),
            total_recos=request_json.get("total_recos", target.total_recos),
        )

        database.targets.remove(target)
        database.targets.add(new_target)

    return Response(
        response=json.dumps(obj=new_target.to_dict()),
        status=HTTPStatus.OK,
    )


if __name__ == "__main__":  # pragma: no cover
    SETTINGS = TargetManagerSettings.model_validate(obj={})
    TARGET_MANAGER_FLASK_APP.run(host=SETTINGS.target_manager_host)
