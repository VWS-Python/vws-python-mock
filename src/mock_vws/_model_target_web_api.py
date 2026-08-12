"""A fake implementation of the Model Target Web API."""

import base64
import io
import json
import uuid
import zipfile
from http import HTTPStatus
from typing import Any, Protocol, runtime_checkable
from urllib.parse import parse_qs

from beartype import beartype

from mock_vws._mock_common import RequestData, json_dump
from mock_vws.model_target import (
    ModelTargetDataset,
    ModelTargetDatasetType,
    ModelTargetGenerationFailure,
    ModelTargetGenerationWarning,
)

_ResponseType = tuple[int, dict[str, str], str | bytes]


@runtime_checkable
class ModelTargetDatasetStore(Protocol):
    """Storage for Model Target datasets."""

    @property
    def model_target_datasets(self) -> dict[str, ModelTargetDataset]:
        """All Model Target datasets, keyed by UUID."""
        # We disable a pylint warning here because the ellipsis is required
        # for pyright to recognize this as a protocol.
        ...  # pylint: disable=unnecessary-ellipsis

    def add_model_target_dataset(
        self,
        model_target_dataset: ModelTargetDataset,
    ) -> None:
        """Add a Model Target dataset."""
        # We disable a pylint warning here because the ellipsis is required
        # for pyright to recognize this as a protocol.
        ...  # pylint: disable=unnecessary-ellipsis

    def remove_model_target_dataset(self, dataset_uuid: str) -> None:
        """Remove a Model Target dataset."""
        # We disable a pylint warning here because the ellipsis is required
        # for pyright to recognize this as a protocol.
        ...  # pylint: disable=unnecessary-ellipsis


_MAX_ADVANCED_MODEL_COUNT = 20
_JWT_DOT_COUNT = 2
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
_MOCK_MODEL_TARGET_CLIENT_ID = "client-id"
_MOCK_MODEL_TARGET_CLIENT_SECRET = "client-secret"  # noqa: S105
# A stable mock value standing in for the user-id segment that real
# Vuforia embeds in some Model Target error targets such as
# ``userId:7635391``. The numeric portion is per-account in real Vuforia;
# the mock uses a fixed placeholder.
_MOCK_USER_TARGET = "userId:mock"
# The CAD data formats documented by the Model Target Web API OpenAPI
# specification.
_CAD_DATA_FORMATS = frozenset(
    {
        "DAE",
        "FBX",
        "GLB",
        "IGES",
        "OBJ",
        "PVZ",
        "STL",
        "VRML",
        "ZIP",
    },
)


@beartype
def _json_response(
    *,
    status_code: HTTPStatus,
    body: dict[str, Any],
) -> _ResponseType:
    """Return a JSON response."""
    body_json = json_dump(body=body)
    return (
        status_code,
        {
            "Content-Length": str(object=len(body_json)),
            "Content-Type": "application/json",
        },
        body_json,
    )


@beartype
def _error_response(
    *,
    status_code: HTTPStatus,
    code: str,
    message: str,
    target: str | None,
    details: list[dict[str, str]] | None,
) -> _ResponseType:
    """Return an error response shaped like the Model Target Web API."""
    error: dict[str, Any] = {"code": code, "message": message}
    if target is not None:
        error["target"] = target
    if details is not None:
        error["details"] = details
    return _json_response(status_code=status_code, body={"error": error})


@beartype
def _validation_error_response(
    *,
    details: list[dict[str, str]],
) -> _ResponseType:
    """Return a Vuforia-style validation error.

    Real Vuforia tags each validation error with a per-request UUID that
    appears in both ``message`` and ``target``. The mock generates a fresh
    UUID so the shape matches.
    """
    request_uuid = uuid.uuid4().hex
    return _error_response(
        status_code=HTTPStatus.BAD_REQUEST,
        code="BAD_REQUEST",
        message=f"Validation error for request {request_uuid}",
        target=request_uuid,
        details=details,
    )


@beartype
def _oauth2_error_response(
    *,
    status_code: HTTPStatus,
    body: dict[str, str],
) -> _ResponseType:
    """Return an OAuth2 error response."""
    return _json_response(status_code=status_code, body=body)


@beartype
def _get_header(request: RequestData, name: str) -> str | None:
    """Return a request header, case-insensitively."""
    lower_name = name.casefold()
    for key, value in request.headers.items():
        if key.casefold() == lower_name:
            return value
    return None


@beartype
def _basic_auth_credentials(auth_header: str | None) -> tuple[str, str] | None:
    """Return HTTP Basic credentials from an authorization header."""
    if auth_header is None or not auth_header.startswith("Basic "):
        return None

    encoded_credentials = auth_header.removeprefix("Basic ").strip()
    try:
        decoded_credentials = base64.b64decode(
            s=encoded_credentials,
            validate=True,
        ).decode(encoding="utf-8")
    except ValueError:
        return None

    client_id, separator, client_secret = decoded_credentials.partition(":")
    if not separator:
        return None

    return client_id, client_secret


@beartype
def _jwt_header_error(*, bearer_token: str) -> str | None:
    """Return the Vuforia error for an invalid JSON Web Token header."""
    encoded_header = bearer_token.partition(".")[0]
    try:
        padding = "=" * (-len(encoded_header) % 4)
        decoded_header = base64.b64decode(
            s=encoded_header + padding,
            altchars=b"-_",
            validate=True,
        )
        header = json.loads(s=decoded_header)
    except ValueError:
        header = None

    if not isinstance(header, dict):
        return "Invalid unsecured/JWS/JWE header: Invalid JSON object"
    if "alg" not in header:
        return 'Missing "alg" in header JSON object'
    if header["alg"] == "none":
        return "Unsecured (plain) JWTs are rejected, extend class to handle"
    return None


@beartype
def _jwt_payload_error(*, bearer_token: str) -> str | None:
    """Return the Vuforia error for an invalid JSON Web Token payload."""
    encoded_payload = bearer_token.split(sep=".")[1]
    try:
        padding = "=" * (-len(encoded_payload) % 4)
        decoded_payload = base64.b64decode(
            s=encoded_payload + padding,
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(s=decoded_payload)
    except ValueError:
        payload = None

    if not isinstance(payload, dict):
        return "Payload of JWS object is not a valid JSON object"
    return None


@beartype
def _jwt_signature_error(*, bearer_token: str) -> str | None:
    """Return the Vuforia error for an invalid JSON Web Token
    signature.
    """
    encoded_signature = bearer_token.rpartition(".")[2]
    if not encoded_signature:
        return "The signature must not be empty"

    try:
        padding = "=" * (-len(encoded_signature) % 4)
        base64.b64decode(
            s=encoded_signature + padding,
            altchars=b"-_",
            validate=True,
        )
    except ValueError:
        return "Signed JWT rejected: Invalid signature"

    return None


@beartype
def _require_bearer_token(request: RequestData) -> _ResponseType | None:
    """Return an error response if the request has no bearer token."""
    auth_header = _get_header(request=request, name="Authorization")
    if auth_header is None or not auth_header.startswith("Bearer "):
        return _error_response(
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message="no Bearer token",
            target="jwt",
            details=None,
        )
    bearer_token = auth_header.removeprefix("Bearer ").strip()
    if not bearer_token:
        return _error_response(
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message="no Bearer token",
            target="jwt",
            details=None,
        )
    if bearer_token.count(".") != _JWT_DOT_COUNT:
        return _error_response(
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message="Invalid JWT serialization: Missing dot delimiter(s)",
            target="jwt",
            details=None,
        )
    jwt_error = _jwt_header_error(bearer_token=bearer_token)
    if jwt_error is None:
        jwt_error = _jwt_payload_error(bearer_token=bearer_token)
    if jwt_error is None:
        jwt_error = _jwt_signature_error(bearer_token=bearer_token)
    if jwt_error is not None:
        return _error_response(
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message=jwt_error,
            target="jwt",
            details=None,
        )
    return None


@beartype
def _fake_jwt(*, token_source: bytes) -> str:
    """Return a deterministic bearer token for the mock."""

    def encode_part(value: dict[str, Any]) -> str:
        """Return a base64url-encoded token part."""
        raw_part = json.dumps(
            obj=value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode(encoding="utf-8")
        return (
            base64.urlsafe_b64encode(s=raw_part)
            .decode(
                encoding="ascii",
            )
            .rstrip("=")
        )

    header = encode_part(value={"alg": "mock", "typ": "JWT"})
    payload = encode_part(
        value={
            "aud": "vuforia-model-target",
            "src": base64.urlsafe_b64encode(s=token_source)
            .decode(
                encoding="ascii",
            )
            .rstrip("="),
        },
    )
    return f"{header}.{payload}.mock-signature"


@beartype
def oauth2_token(request: RequestData) -> _ResponseType:
    """Return a fake OAuth2 access token."""
    auth_header = _get_header(request=request, name="Authorization")
    form = parse_qs(qs=request.body.decode(encoding="utf-8"))
    grant_type = form.get("grant_type", ["client_credentials"])[0]
    if grant_type != "client_credentials":
        return _oauth2_error_response(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"error": "unsupported_grant_type"},
        )

    basic_credentials = _basic_auth_credentials(auth_header=auth_header)
    if basic_credentials is None:
        return _oauth2_error_response(
            status_code=HTTPStatus.UNAUTHORIZED,
            body={
                "error": "invalid_request",
                "error_description": (
                    "Missing or invalid authorization header"
                ),
            },
        )

    if basic_credentials != (
        _MOCK_MODEL_TARGET_CLIENT_ID,
        _MOCK_MODEL_TARGET_CLIENT_SECRET,
    ):
        return _oauth2_error_response(
            status_code=HTTPStatus.UNAUTHORIZED,
            body={"error": "invalid_client"},
        )

    token_source = request.body or (auth_header or "").encode()
    return _json_response(
        status_code=HTTPStatus.OK,
        body={
            "access_token": _fake_jwt(token_source=token_source),
            "token_type": "bearer",
            "expires_in": 3600,
        },
    )


@beartype
def _is_json_object(*, value: object) -> bool:
    """Return whether a decoded JSON value is an object."""
    return isinstance(value, dict)


@beartype
def _load_request_json(request: RequestData) -> dict[str, Any] | _ResponseType:
    """Load a Model Target dataset creation request body."""
    content_type = _get_header(request=request, name="Content-Type") or ""
    if "application/json" not in content_type:
        return _error_response(
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            code="ERROR",
            message="Expecting text/json or application/json body",
            target=None,
            details=None,
        )
    try:
        request_json: dict[str, Any] = json.loads(s=request.body)
    except json.JSONDecodeError as exc:
        return _error_response(
            status_code=HTTPStatus.BAD_REQUEST,
            code="ERROR",
            message=f"Invalid Json: {exc}",
            target=None,
            details=None,
        )
    if not _is_json_object(value=request_json):
        # The required top-level fields are read from the request body, so a
        # body which is valid JSON but not a JSON object is reported as
        # having every required field missing.
        return _validation_error_response(
            details=_top_level_details(request_json={}),
        )
    return request_json


@beartype
def _cad_data_source_details(*, models: list[Any]) -> list[dict[str, str]]:
    """Return validation details for each model's CAD data source.

    One and only one of ``cadDataUrl`` and ``cadDataBlob`` may be given per
    model.
    """
    return [
        {
            "code": "VALIDATION_ERROR",
            "message": (
                f"/models({index}): one and only one of cadDataUrl and "
                "cadDataBlob is required"
            ),
        }
        for index, model in enumerate(iterable=models)
        if ("cadDataUrl" in model) == ("cadDataBlob" in model)
    ]


@beartype
def _model_field_details(*, models: list[Any]) -> list[dict[str, str]]:
    """Return validation details for the fields of each model."""
    missing_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": f"/models({index})/name: element is required",
        }
        for index, model in enumerate(iterable=models)
        if "name" not in model
    ]
    cad_data_source_details = _cad_data_source_details(models=models)
    if missing_details or cad_data_source_details:
        return missing_details + cad_data_source_details

    string_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": f"/models({index})/{field}: error.expected.jsstring",
        }
        for index, model in enumerate(iterable=models)
        for field in ("cadDataBlob", "cadDataFormat", "cadDataUrl", "name")
        if field in model and not isinstance(model[field], str)
    ]
    if string_details:
        return string_details

    format_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": (
                f"/models({index})/cadDataFormat: error.expected.validenum"
            ),
        }
        for index, model in enumerate(iterable=models)
        if "cadDataFormat" in model
        and model["cadDataFormat"] not in _CAD_DATA_FORMATS
    ]
    views_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": f"/models({index})/views: error.expected.jsarray",
        }
        for index, model in enumerate(iterable=models)
        if "views" in model and not isinstance(model["views"], list)
    ]
    return format_details + views_details


@beartype
def _view_details(*, models: list[Any]) -> list[dict[str, str]]:
    """Return validation details for the guide views of each model."""
    views = [
        (model_index, view_index, view)
        for model_index, model in enumerate(iterable=models)
        for view_index, view in enumerate(iterable=model.get("views", []))
    ]

    object_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": (
                f"/models({model_index})/views({view_index}): "
                "error.expected.jsobject"
            ),
        }
        for model_index, view_index, view in views
        if not isinstance(view, dict)
    ]
    if object_details:
        return object_details

    missing_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": (
                f"/models({model_index})/views({view_index})/{field}: "
                "element is required"
            ),
        }
        for model_index, view_index, view in views
        for field in ("guideViewPosition", "name")
        if field not in view
    ]
    if missing_details:
        return missing_details

    name_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": (
                f"/models({model_index})/views({view_index})/name: "
                "error.expected.jsstring"
            ),
        }
        for model_index, view_index, view in views
        if not isinstance(view["name"], str)
    ]
    position_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": (
                f"/models({model_index})/views({view_index})"
                "/guideViewPosition: error.expected.jsobject"
            ),
        }
        for model_index, view_index, view in views
        if not isinstance(view["guideViewPosition"], dict)
    ]
    return name_details + position_details


@beartype
def _is_json_number(*, value: object) -> bool:
    """Return whether a decoded JSON value is a number.

    A JSON boolean decodes to a Python ``bool`` value, which is also an
    ``int`` value, so ``bool`` values are excluded.
    """
    return isinstance(value, int | float) and not isinstance(value, bool)


@beartype
def _guide_view_position_details(
    *,
    models: list[Any],
) -> list[dict[str, str]]:
    """Return validation details for the guide view positions."""
    positions = [
        (model_index, view_index, view["guideViewPosition"])
        for model_index, model in enumerate(iterable=models)
        for view_index, view in enumerate(iterable=model.get("views", []))
    ]

    missing_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": (
                f"/models({model_index})/views({view_index})"
                f"/guideViewPosition/{field}: element is required"
            ),
        }
        for model_index, view_index, position in positions
        for field in ("rotation", "translation")
        if field not in position
    ]
    if missing_details:
        return missing_details

    array_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": (
                f"/models({model_index})/views({view_index})"
                f"/guideViewPosition/{field}: error.expected.jsarray"
            ),
        }
        for model_index, view_index, position in positions
        for field in ("rotation", "translation")
        if not isinstance(position[field], list)
    ]
    if array_details:
        return array_details

    return [
        {
            "code": "VALIDATION_ERROR",
            "message": (
                f"/models({model_index})/views({view_index})"
                f"/guideViewPosition/{field}({element_index}): "
                "error.expected.jsnumber"
            ),
        }
        for model_index, view_index, position in positions
        for field in ("rotation", "translation")
        for element_index, element in enumerate(iterable=position[field])
        if not _is_json_number(value=element)
    ]


@beartype
def _model_count_details(
    *,
    models: list[Any],
    dataset_type: ModelTargetDatasetType,
) -> list[dict[str, str]]:
    """Return validation details for the number of models."""
    model_count = len(models)

    if dataset_type == ModelTargetDatasetType.STANDARD and model_count != 1:
        return [
            {
                "code": "VALIDATION_ERROR",
                "message": "exactly one model should be provided",
            },
        ]

    if (
        dataset_type == ModelTargetDatasetType.ADVANCED
        and not 1 <= model_count <= _MAX_ADVANCED_MODEL_COUNT
    ):
        return [
            {
                "code": "VALIDATION_ERROR",
                "message": (
                    "models must contain between 1 and "
                    f"{_MAX_ADVANCED_MODEL_COUNT} entries"
                ),
            },
        ]

    return []


@beartype
def _top_level_details(
    *,
    request_json: dict[str, Any],
) -> list[dict[str, str]]:
    """Return validation details for the top-level dataset fields."""
    missing_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": f"/{field}: element is required",
        }
        for field in ("models", "name", "targetSdk")
        if field not in request_json
    ]
    if missing_details:
        return missing_details

    type_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": f"/{field}: error.expected.jsstring",
        }
        for field in ("name", "targetSdk")
        if not isinstance(request_json[field], str)
    ]

    models_value = request_json["models"]
    if not isinstance(models_value, list):
        type_details.append(
            {
                "code": "VALIDATION_ERROR",
                "message": "/models: error.expected.jsarray",
            },
        )
        return type_details

    models: list[Any] = [*models_value]
    type_details.extend(
        {
            "code": "VALIDATION_ERROR",
            "message": f"/models({index}): error.expected.jsobject",
        }
        for index, model in enumerate(iterable=models)
        if not isinstance(model, dict)
    )
    return type_details


@beartype
def _validate_dataset_request(
    *,
    request_json: dict[str, Any],
    dataset_type: ModelTargetDatasetType,
) -> _ResponseType | None:
    """Validate the dataset request enough for useful mock feedback."""
    details = _top_level_details(request_json=request_json)
    if not details:
        models: list[Any] = [*request_json["models"]]
        details = (
            _model_field_details(models=models)
            or _view_details(models=models)
            or _guide_view_position_details(models=models)
            or _model_count_details(
                models=models,
                dataset_type=dataset_type,
            )
        )

    if details:
        return _validation_error_response(details=details)

    return None


@beartype
def create_model_target_dataset(
    *,
    request: RequestData,
    dataset_store: ModelTargetDatasetStore,
    processing_time_seconds: float,
    dataset_type: ModelTargetDatasetType,
    generation_failure: ModelTargetGenerationFailure | None,
    generation_warning: ModelTargetGenerationWarning | None,
) -> _ResponseType:
    """Create a standard or advanced Model Target dataset."""
    auth_error = _require_bearer_token(request=request)
    if auth_error is not None:
        return auth_error

    request_json_or_error = _load_request_json(request=request)
    if not isinstance(request_json_or_error, dict):
        return request_json_or_error

    validation_error = _validate_dataset_request(
        request_json=request_json_or_error,
        dataset_type=dataset_type,
    )
    if validation_error is not None:
        return validation_error

    dataset = ModelTargetDataset(
        request_body=request_json_or_error,
        dataset_type=dataset_type,
        processing_time_seconds=processing_time_seconds,
        generation_failure=generation_failure,
        generation_warning=generation_warning,
    )
    dataset_store.add_model_target_dataset(model_target_dataset=dataset)
    return _json_response(
        status_code=HTTPStatus.CREATED,
        body={"uuid": dataset.uuid_},
    )


@beartype
def _unknown_dataset_response(*, dataset_uuid: str) -> _ResponseType:
    """Return the error for a dataset which is not visible to a route."""
    return _error_response(
        status_code=HTTPStatus.NOT_FOUND,
        code="NOT_FOUND",
        message=(
            f"Could not find a model-view database with uuid {dataset_uuid}"
        ),
        target=_MOCK_USER_TARGET,
        details=None,
    )


@beartype
def _find_dataset(
    *,
    dataset_store: ModelTargetDatasetStore,
    dataset_uuid: str,
    dataset_type: ModelTargetDatasetType,
) -> ModelTargetDataset | None:
    """Return a dataset which belongs to a route's dataset type.

    Standard and advanced datasets are separate resources in real Vuforia, so
    a dataset is invisible to the routes of the other dataset type.
    """
    dataset = dataset_store.model_target_datasets.get(dataset_uuid)
    if dataset is None or dataset.dataset_type != dataset_type:
        return None
    return dataset


@beartype
def get_model_target_dataset_status(
    *,
    request: RequestData,
    dataset_store: ModelTargetDatasetStore,
    dataset_uuid: str,
    dataset_type: ModelTargetDatasetType,
) -> _ResponseType:
    """Return the status of a Model Target dataset."""
    auth_error = _require_bearer_token(request=request)
    if auth_error is not None:
        return auth_error
    dataset = _find_dataset(
        dataset_store=dataset_store,
        dataset_uuid=dataset_uuid,
        dataset_type=dataset_type,
    )
    if dataset is None:
        return _unknown_dataset_response(dataset_uuid=dataset_uuid)
    return _json_response(
        status_code=HTTPStatus.OK,
        body=dataset.status_body(),
    )


@beartype
def _dataset_zip_bytes(dataset: ModelTargetDataset) -> bytes:
    """Return a small valid zip file for a generated dataset."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(file=zip_buffer, mode="w") as zip_file:
        dataset_file = zipfile.ZipInfo(
            filename="dataset.json",
            date_time=_ZIP_EPOCH,
        )
        zip_file.writestr(
            zinfo_or_arcname=dataset_file,
            data=json.dumps(
                obj={
                    "uuid": dataset.uuid_,
                    "type": dataset.dataset_type.value,
                    "request": dataset.request_body,
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
        )
    return zip_buffer.getvalue()


@beartype
def download_model_target_dataset(
    *,
    request: RequestData,
    dataset_store: ModelTargetDatasetStore,
    dataset_uuid: str,
    dataset_type: ModelTargetDatasetType,
) -> _ResponseType:
    """Download a generated Model Target dataset."""
    auth_error = _require_bearer_token(request=request)
    if auth_error is not None:
        return auth_error
    dataset = _find_dataset(
        dataset_store=dataset_store,
        dataset_uuid=dataset_uuid,
        dataset_type=dataset_type,
    )
    if dataset is None:
        return _unknown_dataset_response(dataset_uuid=dataset_uuid)
    if dataset.status != "done":
        return _error_response(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code="UNSUPPORTED_STATE",
            message=(
                f"Training status for dataset {dataset_uuid} is "
                "not-started != done"
            ),
            target=dataset_uuid,
            details=None,
        )

    body = _dataset_zip_bytes(dataset=dataset)
    return (
        HTTPStatus.OK,
        {
            "Content-Length": str(object=len(body)),
            "Content-Type": "application/zip",
        },
        body,
    )


@beartype
def delete_model_target_dataset(
    *,
    request: RequestData,
    dataset_store: ModelTargetDatasetStore,
    dataset_uuid: str,
    dataset_type: ModelTargetDatasetType,
) -> _ResponseType:
    """Delete a Model Target dataset."""
    auth_error = _require_bearer_token(request=request)
    if auth_error is not None:
        return auth_error
    dataset = _find_dataset(
        dataset_store=dataset_store,
        dataset_uuid=dataset_uuid,
        dataset_type=dataset_type,
    )
    if dataset is None:
        return _unknown_dataset_response(dataset_uuid=dataset_uuid)
    dataset_store.remove_model_target_dataset(dataset_uuid=dataset_uuid)
    return HTTPStatus.OK, {"Content-Length": "0"}, ""
