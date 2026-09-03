"""Storage layer for the mock Vuforia Flask application."""

import base64
import copy
import datetime
import json
from collections.abc import Callable, Mapping, Sequence
from enum import Enum, StrEnum, auto
from http import HTTPMethod, HTTPStatus
from typing import Annotated, TypeIs, assert_never
from zoneinfo import ZoneInfo

from beartype import beartype
from flask import Flask, Response, request
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    ValidationError,
    model_validator,
)
from pydantic_settings import BaseSettings

from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.database_type import DatabaseType
from mock_vws.model_target import ModelTargetDataset, OAuth2ClientCredential
from mock_vws.request_rate_limits import RequestRateLimit, RequestRateLimits
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


@beartype
def _enum_by_name[T: Enum](*, enum_type: type[T]) -> Callable[[object], T]:
    """Return a validator which looks an enum member up by its name.

    Pydantic validates enums by value, but the target manager API takes
    the member name, such as ``"WORKING"``, so that the request matches
    the response.
    """

    def validate(value: object) -> T:
        """Return the member with the given name."""
        if isinstance(value, str) and value in enum_type.__members__:
            return enum_type[value]
        accepted = ", ".join(repr(name) for name in enum_type.__members__)
        msg = f"Input should be one of {accepted}"
        raise ValueError(msg)

    return validate


_StateName = Annotated[
    States,
    BeforeValidator(func=_enum_by_name(enum_type=States)),
]
_DatabaseTypeName = Annotated[
    DatabaseType,
    BeforeValidator(func=_enum_by_name(enum_type=DatabaseType)),
]


@beartype
def _is_json_object(value: object, /) -> TypeIs[dict[str, object]]:
    """Whether a value parsed from JSON is an object.

    JSON object keys are always strings.
    """
    return isinstance(value, dict)


class RequestRateLimitBody(BaseModel):
    """A single request rate limit in a create cloud database request."""

    model_config = ConfigDict(strict=True, extra="forbid")

    max_requests: int
    window_seconds: float


@beartype
def _to_request_rate_limit(
    *,
    limit: RequestRateLimitBody | None,
) -> RequestRateLimit | None:
    """Create a request rate limit from a request body, or ``None``."""
    if limit is None:
        return None
    return RequestRateLimit(
        max_requests=limit.max_requests,
        window_seconds=limit.window_seconds,
    )


class RequestRateLimitsBody(BaseModel):
    """Per-endpoint request rate limits in a create cloud database
    request.

    A group of endpoints which is not given has no limit of its own.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    other: RequestRateLimitBody | None
    get_target: RequestRateLimitBody | None
    get_duplicates: RequestRateLimitBody | None
    list_targets: RequestRateLimitBody | None

    @model_validator(mode="before")
    @classmethod
    def _treat_missing_limits_as_none(cls, data: object) -> object:
        """Treat a group of endpoints which is not given as having no limit
        of its own.

        The value is whatever was given for ``request_rate_limits``, which
        pydantic validates after this fills in the missing groups.
        """
        if _is_json_object(data):
            return dict.fromkeys(cls.model_fields) | data
        return data

    def to_request_rate_limits(self) -> RequestRateLimits:
        """Create the request rate limits which this body describes."""
        return RequestRateLimits(
            other=_to_request_rate_limit(limit=self.other),
            get_target=_to_request_rate_limit(limit=self.get_target),
            get_duplicates=_to_request_rate_limit(limit=self.get_duplicates),
            list_targets=_to_request_rate_limit(limit=self.list_targets),
        )


class CloudDatabaseRequestBody(BaseModel):
    """The body of a request to create a cloud database.

    The defaults for fields which were not given have been filled in.
    """

    model_config = ConfigDict(strict=True)

    server_access_key: str
    server_secret_key: str
    client_access_key: str
    client_secret_key: str
    database_id: str
    database_name: str
    state_name: _StateName
    database_type_name: _DatabaseTypeName
    request_quota: int
    target_quota: int
    reco_threshold: int
    current_month_recos: int
    previous_month_recos: int
    total_recos: int
    requests_per_second_limit: int | None
    request_rate_limits: RequestRateLimitsBody | None

    def to_cloud_database(self) -> CloudDatabase:
        """Create the cloud database which this body describes."""
        return CloudDatabase(
            server_access_key=self.server_access_key,
            server_secret_key=self.server_secret_key,
            client_access_key=self.client_access_key,
            client_secret_key=self.client_secret_key,
            database_id=self.database_id,
            database_name=self.database_name,
            state=self.state_name,
            database_type=self.database_type_name,
            request_quota=self.request_quota,
            target_quota=self.target_quota,
            reco_threshold=self.reco_threshold,
            current_month_recos=self.current_month_recos,
            previous_month_recos=self.previous_month_recos,
            total_recos=self.total_recos,
            requests_per_second_limit=self.requests_per_second_limit,
            request_rate_limits=(
                None
                if self.request_rate_limits is None
                else self.request_rate_limits.to_request_rate_limits()
            ),
        )


class VuMarkDatabaseRequestBody(BaseModel):
    """The body of a request to create a VuMark database.

    The defaults for fields which were not given have been filled in.
    """

    model_config = ConfigDict(strict=True)

    server_access_key: str
    server_secret_key: str
    database_name: str
    state_name: _StateName

    def to_vumark_database(self) -> VuMarkDatabase:
        """Create the VuMark database which this body describes."""
        return VuMarkDatabase(
            server_access_key=self.server_access_key,
            server_secret_key=self.server_secret_key,
            database_name=self.database_name,
            state=self.state_name,
        )


@beartype
class _InvalidRequestBodyError(Exception):
    """A request body which cannot be used to create a resource.

    Args:
        errors: One entry per problem, in the form which
            :meth:`pydantic.ValidationError.errors` gives: each names the
            location of the problem within the body as ``loc``, which is
            empty when the body as a whole is the problem, and describes it
            in ``msg``.
    """

    def __init__(self, *, errors: Sequence[object]) -> None:
        """Record the problems with the body."""
        super().__init__(errors)
        self.errors = errors


@beartype
def _whole_body_error(*, msg: str) -> dict[str, object]:
    """Describe a problem with a request body as a whole, in the form which
    :meth:`pydantic.ValidationError.errors` gives.
    """
    return {"type": "value_error", "loc": [], "msg": msg}


@beartype
def _validate_request_body[T: BaseModel](
    *,
    model: type[T],
    data: bytes,
    defaults: Mapping[str, object],
) -> T:
    """Parse a request body as a JSON object and validate it as a model.

    Args:
        model: The model to validate the body against.
        data: The raw request body.
        defaults: Values for fields which the body does not give.

    Raises:
        _InvalidRequestBodyError: The body is not a JSON object, or a field
            has a value which the model does not accept.
    """
    try:
        parsed = json.loads(s=data)
    except json.JSONDecodeError as exc:
        raise _InvalidRequestBodyError(
            errors=[_whole_body_error(msg=str(object=exc))],
        ) from exc

    if not _is_json_object(parsed):
        raise _InvalidRequestBodyError(
            errors=[_whole_body_error(msg="Input should be an object")],
        )

    try:
        return model.model_validate(obj=dict(defaults) | parsed)
    except ValidationError as exc:
        raise _InvalidRequestBodyError(
            errors=exc.errors(
                include_url=False,
                include_context=False,
                include_input=False,
            ),
        ) from exc


@beartype
def _bad_request_response(*, errors: Sequence[object]) -> Response:
    """Return a response describing why a request body was rejected.

    The response is a JSON object with an ``errors`` list.
    """
    return Response(
        response=json.dumps(obj={"errors": list(errors)}),
        status=HTTPStatus.BAD_REQUEST,
        mimetype="application/json",
    )


@beartype
def _find_cloud_database(*, database_name: str) -> CloudDatabase | None:
    """Return the cloud database with the given name, if there is one.

    This must be called while holding the target manager's lock.
    """
    for database in TARGET_MANAGER.cloud_databases:
        if database.database_name == database_name:
            return database
    return None


@beartype
def _find_vumark_database(*, database_name: str) -> VuMarkDatabase | None:
    """Return the VuMark database with the given name, if there is one.

    This must be called while holding the target manager's lock.
    """
    for database in TARGET_MANAGER.vumark_databases:
        if database.database_name == database_name:
            return database
    return None


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
        matching_database = _find_cloud_database(database_name=database_name)
        if matching_database is None:
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
        matching_database = _find_vumark_database(database_name=database_name)
        if matching_database is None:
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
    :status 400: The request body is not a JSON object, or a field has a
      value which is not accepted. The response body is a JSON object with
      an ``errors`` list which names each offending field and the accepted
      values.
    :status 409: A cloud database with one of the given keys or the given
      name already exists.
    """
    try:
        body = _validate_request_body(
            model=CloudDatabaseRequestBody,
            data=request.data,
            defaults=CloudDatabase().to_dict(),
        )
    except _InvalidRequestBodyError as exc:
        return _bad_request_response(errors=exc.errors)

    database = body.to_cloud_database()
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

    :reqjson string server_access_key: (Optional) The server access key for the
      VuMark database.

    :reqjson string server_secret_key: (Optional) The server secret key for the
      VuMark database.

    :reqjson string database_name: (Optional) The name of the VuMark database.

    :reqjson string state_name: (Optional) The state of the VuMark database.
     This can be "WORKING", "PROJECT_INACTIVE", "PROJECT_SUSPENDED", or
     "PROJECT_HAS_NO_API_ACCESS". This defaults to "WORKING".

    :status 201: The database has been successfully created.
    :status 400: The request body is not a JSON object, or a field has a
      value which is not accepted. The response body is a JSON object with
      an ``errors`` list which names each offending field and the accepted
      values.
    :status 409: A VuMark database with one of the given keys or the given
      name already exists.
    """
    try:
        body = _validate_request_body(
            model=VuMarkDatabaseRequestBody,
            data=request.data,
            defaults=VuMarkDatabase().to_dict(),
        )
    except _InvalidRequestBodyError as exc:
        return _bad_request_response(errors=exc.errors)

    database = body.to_vumark_database()

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
    """Create a new target in a given cloud database.

    :status 201: The target has been created.
    :status 404: There is no cloud database with the given name.
    """
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
        database = _find_cloud_database(database_name=database_name)
        if database is None:
            return Response(response="", status=HTTPStatus.NOT_FOUND)

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
    """Create a new VuMark target in a given database.

    :status 201: The VuMark target has been created.
    :status 404: There is no VuMark database with the given name.
    """
    request_json = json.loads(s=request.data)
    target = VuMarkTarget.from_dict(target_dict=request_json)
    with TARGET_MANAGER.lock:
        database = _find_vumark_database(database_name=database_name)
        if database is None:
            return Response(response="", status=HTTPStatus.NOT_FOUND)

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
        database = _find_cloud_database(database_name=database_name)
        if database is None:
            return Response(response="", status=HTTPStatus.NOT_FOUND)

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
        database = _find_cloud_database(database_name=database_name)
        if database is None:
            return Response(response="", status=HTTPStatus.NOT_FOUND)

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
        database = _find_cloud_database(database_name=database_name)
        if database is None:
            return Response(response="", status=HTTPStatus.NOT_FOUND)

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
