"""A fake implementation of the Model Target Web API."""

import base64
import io
import json
import uuid
import zipfile
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs

from beartype import beartype

from mock_vws._mock_common import RequestData, json_dump
from mock_vws.model_target import ModelTargetDataset, ModelTargetDatasetType
from mock_vws.target_manager import TargetManager

_ResponseType = tuple[int, dict[str, str], str | bytes]
_MAX_ADVANCED_MODEL_COUNT = 20
_JWT_DOT_COUNT = 2
_MOCK_MODEL_TARGET_CLIENT_ID = "client-id"
_MOCK_MODEL_TARGET_CLIENT_SECRET = "client-secret"  # noqa: S105
# A stable mock value standing in for the user-id segment that real
# Vuforia embeds in some Model Target error targets such as
# ``userId:7635391``. The numeric portion is per-account in real Vuforia;
# the mock uses a fixed placeholder.
_MOCK_USER_TARGET = "userId:mock"


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
    target: str | None = None,
    details: list[dict[str, str]] | None = None,
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
def _require_bearer_token(request: RequestData) -> _ResponseType | None:
    """Return an error response if the request has no bearer token."""
    auth_header = _get_header(request=request, name="Authorization")
    if auth_header is None or not auth_header.startswith("Bearer "):
        return _error_response(
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message="no Bearer token",
            target="jwt",
        )
    bearer_token = auth_header.removeprefix("Bearer ").strip()
    if not bearer_token:
        return _error_response(
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message="no Bearer token",
            target="jwt",
        )
    if bearer_token.count(".") != _JWT_DOT_COUNT:
        return _error_response(
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message="Invalid JWT serialization: Missing dot delimiter(s)",
            target="jwt",
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
def _load_request_json(request: RequestData) -> dict[str, Any] | _ResponseType:
    """Load a Model Target dataset creation request body."""
    content_type = _get_header(request=request, name="Content-Type") or ""
    if "application/json" not in content_type:
        return _error_response(
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            code="ERROR",
            message="Expecting text/json or application/json body",
        )
    try:
        request_json: dict[str, Any] = json.loads(s=request.body)
    except json.JSONDecodeError as exc:
        return _error_response(
            status_code=HTTPStatus.BAD_REQUEST,
            code="ERROR",
            message=f"Invalid Json: {exc}",
        )
    return request_json


@beartype
def _validate_dataset_request(
    *,
    request_json: dict[str, Any],
    dataset_type: ModelTargetDatasetType,
) -> _ResponseType | None:
    """Validate the dataset request enough for useful mock feedback."""
    missing_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": f"/{field}: element is required",
        }
        for field in ("models", "name", "targetSdk")
        if field not in request_json
    ]
    if missing_details:
        return _validation_error_response(details=missing_details)

    models_value = request_json["models"]
    if not isinstance(models_value, list):
        return _validation_error_response(
            details=[
                {
                    "code": "VALIDATION_ERROR",
                    "message": "/models: error.expected.jsarray",
                },
            ],
        )

    models: list[Any] = [*models_value]
    model_count = len(models)

    if dataset_type == ModelTargetDatasetType.STANDARD and model_count != 1:
        return _validation_error_response(
            details=[
                {
                    "code": "VALIDATION_ERROR",
                    "message": "exactly one model should be provided",
                },
            ],
        )

    if (
        dataset_type == ModelTargetDatasetType.ADVANCED
        and not 1 <= model_count <= _MAX_ADVANCED_MODEL_COUNT
    ):
        return _validation_error_response(
            details=[
                {
                    "code": "VALIDATION_ERROR",
                    "message": (
                        "models must contain between 1 and "
                        f"{_MAX_ADVANCED_MODEL_COUNT} entries"
                    ),
                },
            ],
        )

    return None


@beartype
def create_model_target_dataset(
    *,
    request: RequestData,
    target_manager: TargetManager,
    processing_time_seconds: float,
    dataset_type: ModelTargetDatasetType,
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
    )
    target_manager.add_model_target_dataset(model_target_dataset=dataset)
    return _json_response(
        status_code=HTTPStatus.CREATED,
        body={"uuid": dataset.uuid_},
    )


@beartype
def get_model_target_dataset_status(
    *,
    request: RequestData,
    target_manager: TargetManager,
    dataset_uuid: str,
) -> _ResponseType:
    """Return the status of a Model Target dataset."""
    auth_error = _require_bearer_token(request=request)
    if auth_error is not None:
        return auth_error
    try:
        dataset = target_manager.model_target_datasets[dataset_uuid]
    except KeyError:
        return _error_response(
            status_code=HTTPStatus.NOT_FOUND,
            code="NOT_FOUND",
            message=(
                "Could not find a model-view database with uuid "
                f"{dataset_uuid}"
            ),
            target=_MOCK_USER_TARGET,
        )
    return _json_response(
        status_code=HTTPStatus.OK,
        body=dataset.status_body(),
    )


@beartype
def _dataset_zip_bytes(dataset: ModelTargetDataset) -> bytes:
    """Return a small valid zip file for a generated dataset."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(file=zip_buffer, mode="w") as zip_file:
        zip_file.writestr(
            zinfo_or_arcname="dataset.json",
            data=json.dumps(
                obj={
                    "uuid": dataset.uuid_,
                    "type": dataset.dataset_type.value,
                    "request": dataset.request_body,
                },
                separators=(",", ":"),
            ),
        )
    return zip_buffer.getvalue()


@beartype
def download_model_target_dataset(
    *,
    request: RequestData,
    target_manager: TargetManager,
    dataset_uuid: str,
) -> _ResponseType:
    """Download a generated Model Target dataset."""
    auth_error = _require_bearer_token(request=request)
    if auth_error is not None:
        return auth_error
    try:
        dataset = target_manager.model_target_datasets[dataset_uuid]
    except KeyError:
        return _error_response(
            status_code=HTTPStatus.NOT_FOUND,
            code="NOT_FOUND",
            message=(
                "Could not find a model-view database with uuid "
                f"{dataset_uuid}"
            ),
            target=_MOCK_USER_TARGET,
        )
    if dataset.status != "done":
        return _error_response(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code="UNSUPPORTED_STATE",
            message=(
                f"Training status for dataset {dataset_uuid} is "
                "not-started != done"
            ),
            target=dataset_uuid,
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
    target_manager: TargetManager,
    dataset_uuid: str,
) -> _ResponseType:
    """Delete a Model Target dataset."""
    auth_error = _require_bearer_token(request=request)
    if auth_error is not None:
        return auth_error
    try:
        target_manager.remove_model_target_dataset(dataset_uuid=dataset_uuid)
    except KeyError:
        return _error_response(
            status_code=HTTPStatus.NOT_FOUND,
            code="NOT_FOUND",
            message=(
                "Could not find a model-view database with uuid "
                f"{dataset_uuid}"
            ),
            target=_MOCK_USER_TARGET,
        )
    return HTTPStatus.OK, {"Content-Length": "0"}, ""
