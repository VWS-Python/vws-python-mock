"""A fake implementation of the Model Target Web API."""

import base64
import io
import json
import secrets
import uuid
import zipfile
from http import HTTPStatus
from typing import Any, Protocol, runtime_checkable
from urllib.parse import parse_qs

from beartype import beartype

from mock_vws._mock_common import RequestData, json_dump
from mock_vws._services_validators.exceptions import (
    ContentLengthHeaderNotIntError,
)
from mock_vws.model_target import (
    ModelTargetDataset,
    ModelTargetDatasetType,
    ModelTargetGenerationFailure,
    ModelTargetGenerationWarning,
    OAuth2ClientCredential,
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

    @property
    def oauth2_client_credentials(self) -> dict[str, OAuth2ClientCredential]:
        """All dynamically created OAuth2 client credentials."""
        ...  # pylint: disable=unnecessary-ellipsis

    def add_oauth2_client_credential(
        self,
        credential: OAuth2ClientCredential,
    ) -> None:
        """Add an OAuth2 client credential."""
        ...  # pylint: disable=unnecessary-ellipsis

    def remove_oauth2_client_credential(self, client_id: str) -> None:
        """Remove an OAuth2 client credential."""
        ...  # pylint: disable=unnecessary-ellipsis


_MAX_ADVANCED_MODEL_COUNT = 20
_JWT_DOT_COUNT = 2
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
_MOCK_MODEL_TARGET_CLIENT_ID = "client-id"
_MOCK_MODEL_TARGET_CLIENT_SECRET = "client-secret"  # noqa: S105
_MOCK_MODEL_TARGET_USERNAME = "user@example.com"
_MOCK_MODEL_TARGET_PASSWORD = "password"  # noqa: S105
_MODEL_TARGET_SCOPES = frozenset(
    {
        "modeltargets.all",
        "modeltargets.standardmodeltarget.all",
        "modeltargets.advancedmodeltarget.all",
        "modeltargets.statebasedmodeltarget.all",
        "modeltargets.advancedstatebasedmodeltarget.all",
    },
)
_CLIENT_CREDENTIALS_SCOPE = "oauth2.clientcredentials.all"
_MAX_CLIENT_CREDENTIALS = 100
# A stable mock value standing in for the user-id segment that real
# Vuforia embeds in some Model Target error targets such as
# ``userId:7635391``. The numeric portion is per-account in real Vuforia;
# the mock uses a fixed placeholder.
_MOCK_USER_TARGET = "userId:mock"
# The enumerated model field values documented by the Model Target Web API
# OpenAPI specification.
_MODEL_ENUM_FIELD_VALUES: dict[str, frozenset[str]] = {
    "automaticColoring": frozenset({"always", "auto", "never"}),
    "cadDataFormat": frozenset(
        {
            "DAE",
            "DRC_GLB",
            "DRC_GLTF",
            "FBX",
            "GLB",
            "IGES",
            "OBJ",
            "PVS",
            "PVZ",
            "STL",
            "VRML",
            "ZIP",
        },
    ),
    "motionHint": frozenset({"adaptive", "dynamic", "static"}),
    "optimizeTrackingFor": frozenset(
        {"ar_controller", "default", "low_feature_objects"},
    ),
    "simplify": frozenset({"always", "auto", "never"}),
    "trackingMode": frozenset({"car", "default", "scan"}),
}
# The training status which the download route reports for a dataset which
# is not ready to download, keyed by the status which the status route
# reports.
#
# Real Vuforia reports ``not-started`` for a dataset which was created just
# before the download request, so the mock uses that name for the whole
# processing window. The name for a dataset whose generation failed has not
# been observed.
_TRAINING_STATUSES: dict[str, str] = {
    "processing": "not-started",
    "failed": "failed",
}
# ``realisticAppearance`` is documented as an enumerated model field for
# advanced datasets only.
_ADVANCED_MODEL_ENUM_FIELD_VALUES: dict[str, frozenset[str]] = {
    **_MODEL_ENUM_FIELD_VALUES,
    "realisticAppearance": frozenset({"auto", "false", "true"}),
}


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
def _content_length_error(request: RequestData) -> _ResponseType | None:
    """Return an error response if ``Content-Length`` is not an integer.

    The load balancer in front of real Vuforia rejects a request with a
    ``Content-Length`` header which is not an integer before the request
    reaches any API, so the Model Target Web API gives the same response
    as the VWS API does.

    A ``Content-Length`` header which is too large is not handled here.
    Real Vuforia waits for the body it was promised and then times out,
    which is too slow to verify in a test.
    """
    given_content_length = _get_header(request=request, name="Content-Length")
    if given_content_length is None:
        return None

    try:
        int(given_content_length)
    except ValueError:
        error = ContentLengthHeaderNotIntError()
        return (error.status_code, dict(error.headers), error.response_text)

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
def _jwt_scopes(*, bearer_token: str) -> frozenset[str]:
    """Return the scopes carried by a valid mock JWT."""
    encoded_payload = bearer_token.split(sep=".")[1]
    padding = "=" * (-len(encoded_payload) % 4)
    payload = json.loads(
        s=base64.b64decode(
            s=encoded_payload + padding,
            altchars=b"-_",
            validate=True,
        ),
    )
    scope = payload.get("scope", "")
    if not isinstance(scope, str):
        return frozenset()
    return frozenset(scope.split())


@beartype
def _require_bearer_token(
    request: RequestData,
    dataset_type: ModelTargetDatasetType,
) -> _ResponseType | None:
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
    required_scope = (
        "modeltargets.standardmodeltarget.all"
        if dataset_type == ModelTargetDatasetType.STANDARD
        else "modeltargets.advancedmodeltarget.all"
    )
    scopes = _jwt_scopes(bearer_token=bearer_token)
    if required_scope not in scopes and "modeltargets.all" not in scopes:
        body = "User does not have the required scopes to perform this action"
        return (
            HTTPStatus.FORBIDDEN,
            {
                "Content-Length": str(object=len(body)),
                "Content-Type": "text/plain",
            },
            body,
        )
    return None


@beartype
def _require_state_based_scope(
    request: RequestData,
    dataset_type: ModelTargetDatasetType,
) -> _ResponseType | None:
    """Return an error when a token lacks the State-Based MT scope."""
    auth_header = _get_header(request=request, name="Authorization")
    assert auth_header is not None  # noqa: S101
    bearer_token = auth_header.removeprefix("Bearer ").strip()
    required_scope = (
        "modeltargets.statebasedmodeltarget.all"
        if dataset_type == ModelTargetDatasetType.STANDARD
        else "modeltargets.advancedstatebasedmodeltarget.all"
    )
    scopes = _jwt_scopes(bearer_token=bearer_token)
    if required_scope in scopes or "modeltargets.all" in scopes:
        return None
    return _error_response(
        status_code=HTTPStatus.FORBIDDEN,
        code="ERROR",
        message="User not allowed to create State Based Model Targets",
        target=_MOCK_USER_TARGET,
        details=None,
    )


@beartype
def _fake_jwt(*, token_source: bytes, scopes: frozenset[str]) -> str:
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
            "scope": " ".join(sorted(scopes)),
        },
    )
    return f"{header}.{payload}.mock-signature"


@beartype
def oauth2_token(  # noqa: PLR0911
    *,
    request: RequestData,
    credential_store: ModelTargetDatasetStore,
) -> _ResponseType:
    """Return a fake OAuth2 access token."""
    content_length_error = _content_length_error(request=request)
    if content_length_error is not None:
        return content_length_error

    auth_header = _get_header(request=request, name="Authorization")
    # A form body which is not valid UTF-8 is decoded leniently rather than
    # raising, so that a body which cannot be decoded is treated as one which
    # does not name a grant type.
    form = parse_qs(
        qs=request.body.decode(encoding="utf-8", errors="replace"),
    )
    grant_type = form.get("grant_type", ["client_credentials"])[0]
    if grant_type not in {"client_credentials", "password"}:
        return _oauth2_error_response(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"error": "unsupported_grant_type"},
        )

    dynamic_credential: OAuth2ClientCredential | None = None
    if grant_type == "client_credentials":
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

        dynamic_credential = credential_store.oauth2_client_credentials.get(
            basic_credentials[0],
        )
        fixed_credential_matches = basic_credentials == (
            _MOCK_MODEL_TARGET_CLIENT_ID,
            _MOCK_MODEL_TARGET_CLIENT_SECRET,
        )
        dynamic_credential_matches = (
            dynamic_credential is not None
            and dynamic_credential.client_secret == basic_credentials[1]
        )
        if not fixed_credential_matches and not dynamic_credential_matches:
            return _oauth2_error_response(
                status_code=HTTPStatus.UNAUTHORIZED,
                body={"error": "invalid_client"},
            )
    else:
        username = form.get("username", [""])[0]
        password = form.get("password", [""])[0]
        if not username or not password:
            return _oauth2_error_response(
                status_code=HTTPStatus.BAD_REQUEST,
                body={
                    "error": "invalid_request",
                    "error_description": "Missing username and/or password",
                },
            )
        if (username, password) != (
            _MOCK_MODEL_TARGET_USERNAME,
            _MOCK_MODEL_TARGET_PASSWORD,
        ):
            return _oauth2_error_response(
                status_code=HTTPStatus.UNAUTHORIZED,
                body={
                    "error": "invalid_grant",
                    "error_description": "Invalid username and/or password",
                },
            )

    token_source = request.body or (auth_header or "").encode()
    requested_scope = form.get("scope", [""])[0]
    if grant_type == "client_credentials" and dynamic_credential is not None:
        credential_scopes = frozenset(dynamic_credential.scopes)
    else:
        credential_scopes = _MODEL_TARGET_SCOPES | {
            _CLIENT_CREDENTIALS_SCOPE,
        }
    scopes = frozenset(requested_scope.split()) or credential_scopes
    if not scopes.issubset(credential_scopes):
        return _oauth2_error_response(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"error": "invalid_scope"},
        )
    return _json_response(
        status_code=HTTPStatus.OK,
        body={
            "access_token": _fake_jwt(
                token_source=token_source,
                scopes=scopes,
            ),
            "token_type": "bearer",
            "expires_in": 3600,
        },
    )


@beartype
def _require_client_credentials_scope(
    request: RequestData,
) -> _ResponseType | None:
    """Require a valid bearer token with the credential-management
    scope.
    """
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
    if bearer_token.count(".") != _JWT_DOT_COUNT:
        return _error_response(
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message="Invalid JWT serialization: Missing dot delimiter(s)",
            target="jwt",
            details=None,
        )
    jwt_error = (
        _jwt_header_error(bearer_token=bearer_token)
        or _jwt_payload_error(bearer_token=bearer_token)
        or _jwt_signature_error(bearer_token=bearer_token)
    )
    if jwt_error is not None:
        return _error_response(
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message=jwt_error,
            target="jwt",
            details=None,
        )
    if _CLIENT_CREDENTIALS_SCOPE not in _jwt_scopes(
        bearer_token=bearer_token,
    ):
        body = "User does not have the required scopes to perform this action"
        return (
            HTTPStatus.FORBIDDEN,
            {
                "Content-Length": str(object=len(body)),
                "Content-Type": "text/plain",
            },
            body,
        )
    return None


@beartype
def _client_credential_not_found(*, client_id: str) -> _ResponseType:
    """Return Vuforia's missing-client-credential response."""
    return _error_response(
        status_code=HTTPStatus.NOT_FOUND,
        code="NOT_FOUND",
        message=f"Clientcredential with ID={client_id} not found",
        target="clientcredential",
        details=None,
    )


@beartype
def _string_list(value: object) -> list[str] | None:
    """Return a string list when ``value`` contains only strings."""
    if not isinstance(value, list):
        return None
    strings: list[str] = []
    for item in value:  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(item, str):
            return None
        strings.append(item)
    return strings


@beartype
def create_oauth2_client_credential(
    *,
    request: RequestData,
    credential_store: ModelTargetDatasetStore,
) -> _ResponseType:
    """Create an OAuth2 client credential."""
    auth_error = _require_client_credentials_scope(request=request)
    if auth_error is not None:
        return auth_error
    request_json_or_error = _load_request_json(request=request)
    if not isinstance(request_json_or_error, dict):
        return request_json_or_error
    scopes = _string_list(value=request_json_or_error.get("scopes"))
    if scopes is None:
        return _validation_error_response(
            details=[
                {
                    "code": "VALIDATION_ERROR",
                    "message": "/scopes: error.expected.jsarray",
                },
            ],
        )
    if len(credential_store.oauth2_client_credentials) >= (
        _MAX_CLIENT_CREDENTIALS
    ):
        return _error_response(
            status_code=HTTPStatus.CONFLICT,
            code="CONFLICT",
            message="Maximum number of client credentials reached",
            target="clientcredential",
            details=None,
        )
    client_id = uuid.uuid4().hex.upper()[:21]
    client_secret = secrets.token_urlsafe(nbytes=25)[:33]
    credential_store.add_oauth2_client_credential(
        credential=OAuth2ClientCredential(
            client_id=client_id,
            client_secret=client_secret,
            scopes=tuple(scopes),
        ),
    )
    return _json_response(
        status_code=HTTPStatus.CREATED,
        body={"client_id": client_id, "client_secret": client_secret},
    )


@beartype
def list_oauth2_client_credentials(
    *,
    request: RequestData,
    credential_store: ModelTargetDatasetStore,
) -> _ResponseType:
    """List OAuth2 client credentials."""
    auth_error = _require_client_credentials_scope(request=request)
    if auth_error is not None:
        return auth_error
    credentials = [
        {"clientId": credential.client_id, "scopes": list(credential.scopes)}
        for credential in credential_store.oauth2_client_credentials.values()
    ]
    body = json.dumps(obj=credentials, separators=(",", ":"))
    return (
        HTTPStatus.OK,
        {
            "Content-Length": str(object=len(body)),
            "Content-Type": "application/json",
        },
        body,
    )


@beartype
def update_oauth2_client_credential_scopes(
    *,
    request: RequestData,
    credential_store: ModelTargetDatasetStore,
    client_id: str,
) -> _ResponseType:
    """Replace the scopes assigned to an OAuth2 client credential."""
    auth_error = _require_client_credentials_scope(request=request)
    if auth_error is not None:
        return auth_error
    credential = credential_store.oauth2_client_credentials.get(client_id)
    if credential is None:
        return _client_credential_not_found(client_id=client_id)
    try:
        scopes_value: object = json.loads(s=request.body)
    except UnicodeDecodeError, json.JSONDecodeError:
        scopes_value = None
    scopes = _string_list(value=scopes_value)
    if scopes is None:
        return _error_response(
            status_code=HTTPStatus.BAD_REQUEST,
            code="BAD_REQUEST",
            message="Invalid scopes",
            target="scopes",
            details=None,
        )
    credential_store.add_oauth2_client_credential(
        credential=OAuth2ClientCredential(
            client_id=credential.client_id,
            client_secret=credential.client_secret,
            scopes=tuple(scopes),
        ),
    )
    return _json_response(
        status_code=HTTPStatus.OK,
        body={"clientId": client_id, "scopes": scopes},
    )


@beartype
def delete_oauth2_client_credential(
    *,
    request: RequestData,
    credential_store: ModelTargetDatasetStore,
    client_id: str,
) -> _ResponseType:
    """Delete an OAuth2 client credential."""
    auth_error = _require_client_credentials_scope(request=request)
    if auth_error is not None:
        return auth_error
    if client_id not in credential_store.oauth2_client_credentials:
        return _client_credential_not_found(client_id=client_id)
    credential_store.remove_oauth2_client_credential(client_id=client_id)
    return HTTPStatus.NO_CONTENT, {"Content-Length": "0"}, ""


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
        request_json: dict[str, Any] = json.loads(
            s=request.body.decode(encoding="utf-8"),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
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

    One and only one of ``cadDataUrl``, ``cadDataBlob`` and ``cadDataUuid``
    may be given per model.
    """
    return [
        {
            "code": "VALIDATION_ERROR",
            "message": (
                f"model '{model['name']}' is invalid. "
                + (
                    "One of `cadDataBlob`, `cadDataUrl`, `cadDataUuid` need "
                    "to be provided"
                    if not sources
                    else "Only one of `cadDataBlob`, `cadDataUrl`, "
                    "`cadDataUuid` need to be provided"
                )
            ),
        }
        for model in models
        if len(
            sources := {
                field
                for field in ("cadDataBlob", "cadDataUrl", "cadDataUuid")
                if field in model
            },
        )
        != 1
    ]


@beartype
def _model_field_details(
    *,
    models: list[Any],
    dataset_type: ModelTargetDatasetType,
) -> list[dict[str, str]]:
    """Return validation details for the fields of each model."""
    enum_field_values = (
        _ADVANCED_MODEL_ENUM_FIELD_VALUES
        if dataset_type == ModelTargetDatasetType.ADVANCED
        else _MODEL_ENUM_FIELD_VALUES
    )
    missing_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": f"/models({index})/{field}: element is required",
        }
        for index, model in enumerate(iterable=models)
        for field in ("name", "views")
        if field not in model
    ]
    if missing_details:
        return missing_details

    cad_data_source_details = _cad_data_source_details(models=models)
    if cad_data_source_details:
        return cad_data_source_details

    string_fields = sorted(
        {
            "cadDataBlob",
            "cadDataUrl",
            "name",
            "stateBasedConfigurationJsonString",
            *enum_field_values,
        },
    )
    string_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": f"/models({index})/{field}: error.expected.jsstring",
        }
        for index, model in enumerate(iterable=models)
        for field in string_fields
        if field in model and not isinstance(model[field], str)
    ]
    if string_details:
        return string_details

    enum_details: list[dict[str, str]] = []
    for index, model in enumerate(iterable=models):
        for field, allowed_values in sorted(enum_field_values.items()):
            if field in {"motionHint", "trackingMode"}:
                continue
            if field not in model or model[field] in allowed_values:
                continue
            value = model[field]
            messages = {
                "automaticColoring": (
                    "invalid automaticColoring. Should be one of 'never', "
                    f"'always', 'auto'. You provided '{value}'"
                ),
                "cadDataFormat": (
                    "Unrecognized cadDataFormat '"
                    f"{str(object=value).upper()}'.  "
                    "Allowed values are: ZIP, GLB, DRC_GLB, DRC_GLTF, DAE, "
                    "FBX, IGES, OBJ, PVS, PVZ, STL, VRML, or specify no "
                    "cadDataFormat to auto-detect GLB and zipped glTFs."
                ),
                "optimizeTrackingFor": (
                    "`optimizeTrackingFor` must be one of "
                    "default,low_feature_objects,ar_controller"
                ),
                "realisticAppearance": (
                    '`realisticAppearance` must be one of "true", "false", '
                    '"auto".` '
                ),
                "simplify": (
                    "invalid simplify. Should be one of 'never', 'always', "
                    f"'auto'. You provided 'Some({value})'"
                ),
            }
            message = messages.get(
                field,
                f"/models({index})/{field}: error.expected.validenum",
            )
            enum_details.append(
                {"code": "VALIDATION_ERROR", "message": message},
            )
        if "motionHint" in model or "trackingMode" in model:
            enum_details.append(
                {
                    "code": "VALIDATION_ERROR",
                    "message": (
                        "`motionHint` and `trackingMode` are no longer "
                        "supported when using `targetsSdk` 10.9 or later. "
                        "Please use the `optimizeTrackingFor` setting instead."
                    ),
                },
            )
    views_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": f"/models({index})/views: error.expected.jsarray",
        }
        for index, model in enumerate(iterable=models)
        if "views" in model and not isinstance(model["views"], list)
    ]
    return enum_details + views_details


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
        for field in ("name",)
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
        if "guideViewPosition" in view
        and not isinstance(view["guideViewPosition"], dict)
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
        if "guideViewPosition" in view
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
def _configuration_states(
    *,
    model_index: int,
    configuration_string: str,
) -> tuple[frozenset[str] | None, dict[str, str] | None]:
    """Load the state names from a State-Based Model Target config."""
    try:
        configuration: Any = json.loads(s=configuration_string)
    except json.JSONDecodeError:
        return None, {
            "code": "VALIDATION_ERROR",
            "message": (
                f"/models({model_index})/stateBasedConfigurationJsonString: "
                "error.expected.validjson"
            ),
        }
    if not _is_json_object(value=configuration):
        return None, {
            "code": "VALIDATION_ERROR",
            "message": (
                f"/models({model_index})/stateBasedConfigurationJsonString/"
                "states: error.expected.jsobject"
            ),
        }
    configuration_states_value: object = configuration.get("states")
    if not _is_json_object(value=configuration_states_value):
        return None, {
            "code": "VALIDATION_ERROR",
            "message": (
                f"/models({model_index})/stateBasedConfigurationJsonString/"
                "states: error.expected.jsobject"
            ),
        }
    configuration_states: dict[str, Any] = configuration["states"]
    state_names = frozenset(configuration_states)
    return state_names, None


@beartype
def _state_based_details(*, models: list[Any]) -> list[dict[str, str]]:
    """Return validation details for State-Based Model Targets."""
    state_fields = [
        (model_index, view_index, view["states"])
        for model_index, model in enumerate(iterable=models)
        for view_index, view in enumerate(iterable=model.get("views", []))
        if "states" in view
    ]
    array_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": (
                f"/models({model_index})/views({view_index})/states: "
                "error.expected.jsarray"
            ),
        }
        for model_index, view_index, states in state_fields
        if not isinstance(states, list)
    ]
    if array_details:
        return array_details

    element_details = [
        {
            "code": "VALIDATION_ERROR",
            "message": (
                f"/models({model_index})/views({view_index})/states"
                f"({state_index}): error.expected.jsstring"
            ),
        }
        for model_index, view_index, states in state_fields
        for state_index, state in enumerate(iterable=states)
        if not isinstance(state, str)
    ]
    if element_details:
        return element_details

    details: list[dict[str, str]] = []
    configured_states: dict[int, frozenset[str]] = {}
    for model_index, model in enumerate(iterable=models):
        configuration_string = model.get("stateBasedConfigurationJsonString")
        if not isinstance(configuration_string, str):
            continue
        state_names, detail = _configuration_states(
            model_index=model_index,
            configuration_string=configuration_string,
        )
        if detail is not None:
            details.append(detail)
        if state_names is not None:
            configured_states[model_index] = state_names

    if details:
        return details

    for model_index, view_index, states in state_fields:
        if model_index not in configured_states:
            details.append(
                {
                    "code": "VALIDATION_ERROR",
                    "message": (
                        f"/models({model_index})/"
                        "stateBasedConfigurationJsonString: element is "
                        "required when view states are given"
                    ),
                },
            )
            continue
        details.extend(
            {
                "code": "VALIDATION_ERROR",
                "message": (
                    "states in entrypoint "
                    f"{models[model_index]['views'][view_index]['name']}' "
                    "must be a subset of all states"
                ),
            }
            for state in states
            if state not in configured_states[model_index]
        )

    return details


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

    if dataset_type == ModelTargetDatasetType.ADVANCED:
        details: list[dict[str, str]] = []
        names = [model["name"] for model in models]
        if len(set(names)) != len(names):
            details.append(
                {
                    "code": "VALIDATION_ERROR",
                    "message": (
                        "names of models must be unique within a Target."
                    ),
                },
            )
        if model_count > _MAX_ADVANCED_MODEL_COUNT:
            details.append(
                {
                    "code": "VALIDATION_ERROR",
                    "message": (
                        "total number of models must be maximum "
                        f"{_MAX_ADVANCED_MODEL_COUNT}"
                    ),
                },
            )
        if model_count == 0:
            details.append(
                {
                    "code": "VALIDATION_ERROR",
                    "message": "models must contain at least one entry",
                },
            )
        return details

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
        # Vuforia's schema validator reads fields from non-object model and
        # view values as though they were empty objects.
        models: list[Any] = [
            model if isinstance(model, dict) else {}
            for model in request_json["models"]
        ]
        for model in models:
            if isinstance(model.get("views"), list):
                model["views"] = [
                    view if isinstance(view, dict) else {}
                    for view in model["views"]
                ]
        details = (
            _model_field_details(models=models, dataset_type=dataset_type)
            or _view_details(models=models)
            or _guide_view_position_details(models=models)
            or _state_based_details(models=models)
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
    content_length_error = _content_length_error(request=request)
    if content_length_error is not None:
        return content_length_error

    auth_error = _require_bearer_token(
        request=request,
        dataset_type=dataset_type,
    )
    if auth_error is not None:
        return auth_error

    request_json_or_error = _load_request_json(request=request)
    if not isinstance(request_json_or_error, dict):
        return request_json_or_error

    models_value = request_json_or_error.get("models")
    is_state_based = isinstance(models_value, list) and any(
        isinstance(model, dict)
        and "stateBasedConfigurationJsonString" in model
        for model in models_value  # pyright: ignore[reportUnknownVariableType]
    )
    if is_state_based:
        state_scope_error = _require_state_based_scope(
            request=request,
            dataset_type=dataset_type,
        )
        if state_scope_error is not None:
            return state_scope_error

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
) -> ModelTargetDataset | None:
    """Return a Model Target dataset by UUID."""
    return dataset_store.model_target_datasets.get(dataset_uuid)


@beartype
def get_model_target_dataset_status(
    *,
    request: RequestData,
    dataset_store: ModelTargetDatasetStore,
    dataset_uuid: str,
    dataset_type: ModelTargetDatasetType,
) -> _ResponseType:
    """Return the status of a Model Target dataset."""
    content_length_error = _content_length_error(request=request)
    if content_length_error is not None:
        return content_length_error

    auth_error = _require_bearer_token(
        request=request,
        dataset_type=dataset_type,
    )
    if auth_error is not None:
        return auth_error
    dataset = _find_dataset(
        dataset_store=dataset_store,
        dataset_uuid=dataset_uuid,
    )
    if dataset is None:
        return _unknown_dataset_response(dataset_uuid=dataset_uuid)
    return _json_response(
        status_code=HTTPStatus.OK,
        body=dataset.status_body(),
    )


@beartype
def _dataset_zip_bytes(dataset: ModelTargetDataset) -> bytes:
    """Return a deterministic Vuforia-shaped generated dataset zip."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(file=zip_buffer, mode="w") as zip_file:
        dat_file = zipfile.ZipInfo(
            filename="MTDataset.dat",
            date_time=_ZIP_EPOCH,
        )
        zip_file.writestr(
            zinfo_or_arcname=dat_file,
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
        xml_file = zipfile.ZipInfo(
            filename="MTDataset.xml",
            date_time=_ZIP_EPOCH,
        )
        zip_file.writestr(
            zinfo_or_arcname=xml_file,
            data=(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<QCARConfig xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                "<Tracking /></QCARConfig>"
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
    content_length_error = _content_length_error(request=request)
    if content_length_error is not None:
        return content_length_error

    auth_error = _require_bearer_token(
        request=request,
        dataset_type=dataset_type,
    )
    if auth_error is not None:
        return auth_error
    dataset = _find_dataset(
        dataset_store=dataset_store,
        dataset_uuid=dataset_uuid,
    )
    if dataset is None:
        return _unknown_dataset_response(dataset_uuid=dataset_uuid)
    if dataset.status != "done":
        training_status = _TRAINING_STATUSES[dataset.status]
        return _error_response(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code="UNSUPPORTED_STATE",
            message=(
                f"Training status for dataset {dataset_uuid} is "
                f"{training_status} != done"
            ),
            target=dataset_uuid,
            details=None,
        )

    body = _dataset_zip_bytes(dataset=dataset)
    return (
        HTTPStatus.OK,
        {
            "Content-Length": str(object=len(body)),
            "Content-Disposition": "attachment; filename=full-dataset.zip",
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
    content_length_error = _content_length_error(request=request)
    if content_length_error is not None:
        return content_length_error

    auth_error = _require_bearer_token(
        request=request,
        dataset_type=dataset_type,
    )
    if auth_error is not None:
        return auth_error
    dataset = _find_dataset(
        dataset_store=dataset_store,
        dataset_uuid=dataset_uuid,
    )
    if dataset is None:
        return _unknown_dataset_response(dataset_uuid=dataset_uuid)
    if dataset.dataset_type != dataset_type:
        # Real Vuforia returns success when deleting through the other route,
        # but leaves the dataset available through its creation route.
        return HTTPStatus.OK, {"Content-Length": "0"}, ""
    dataset_store.remove_model_target_dataset(dataset_uuid=dataset_uuid)
    return HTTPStatus.OK, {"Content-Length": "0"}, ""
