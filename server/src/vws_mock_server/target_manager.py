"""Storage layer for the mock Vuforia Flask application."""

import json
from collections.abc import Callable, Sequence
from enum import Enum
from http import HTTPMethod, HTTPStatus
from typing import (
    Annotated,
    ClassVar,
    TypedDict,
    TypeIs,
)

from beartype import beartype
from flask import Flask, Response, request
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    JsonValue,
    ValidationError,
)
from pydantic_settings import BaseSettings

from mock_vws.database import (
    VuMarkDatabase,
    VuMarkDatabaseDict,
)
from mock_vws.model_target import (
    ModelTargetDataset,
    OAuth2ClientCredential,
)
from mock_vws.states import States
from mock_vws.target import VuMarkTarget
from mock_vws.target_manager import TargetManager

TARGET_MANAGER_FLASK_APP = Flask(import_name=__name__, static_folder=None)

TARGET_MANAGER = TargetManager()


@beartype
class TargetManagerSettings(BaseSettings):
    """Settings for the Target Manager Flask app."""

    target_manager_host: str = ""


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


@beartype
def _is_json_object(value: object, /) -> TypeIs[dict[str, JsonValue]]:
    """Whether a value parsed from JSON is an object.

    JSON object keys are always strings.
    """
    return isinstance(value, dict)


@beartype
class VuMarkDatabaseRequestBody(BaseModel):
    """The body of a request to create a VuMark database.

    The defaults for fields which were not given have been filled in.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(strict=True)

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


class OAuth2ClientCredentialBody(BaseModel):
    """A request to register an OAuth2 client credential."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        strict=True, extra="forbid"
    )

    client_id: str
    client_secret: str
    scopes: tuple[str, ...]


class _RequestBodyError(TypedDict):
    """A JSON-serializable request-body validation error."""

    type: str
    loc: list[int | str]
    msg: str


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

    def __init__(self, *, errors: Sequence[_RequestBodyError]) -> None:
        """Record the problems with the body."""
        super().__init__(errors)
        self.errors = errors


@beartype
def _whole_body_error(*, msg: str) -> _RequestBodyError:
    """Describe a problem with a request body as a whole, in the form which
    :meth:`pydantic.ValidationError.errors` gives.
    """
    return {"type": "value_error", "loc": [], "msg": msg}


@beartype
def _request_body_errors(*, error: ValidationError) -> list[_RequestBodyError]:
    """Return Pydantic validation problems in the target manager shape."""
    errors: list[_RequestBodyError] = []
    for item in error.errors(
        include_url=False,
        include_context=False,
        include_input=False,
    ):
        loc = list(item["loc"])
        errors.append(
            {"type": item["type"], "loc": loc, "msg": item["msg"]},
        )
    return errors


@beartype
def _validate_request_body[T: BaseModel](
    *,
    model: type[T],
    data: bytes,
    defaults: VuMarkDatabaseDict,
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
            errors=_request_body_errors(error=exc),
        ) from exc


@beartype
def _bad_request_response(*, errors: Sequence[_RequestBodyError]) -> Response:
    """Return a response describing why a request body was rejected.

    The response is a JSON object with an ``errors`` list.
    """
    return Response(
        response=json.dumps(obj={"errors": list(errors)}),
        status=HTTPStatus.BAD_REQUEST,
        mimetype="application/json",
    )


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
    value = OAuth2ClientCredentialBody.model_validate_json(
        json_data=request.data,
    )
    credential = OAuth2ClientCredential(
        client_id=value.client_id,
        client_secret=value.client_secret,
        scopes=value.scopes,
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


# Containers execute this process entry point; import-driven tests use its API.
if __name__ == "__main__":  # pragma: no cover
    SETTINGS = TargetManagerSettings.model_validate(obj={})
    TARGET_MANAGER_FLASK_APP.run(host=SETTINGS.target_manager_host)
