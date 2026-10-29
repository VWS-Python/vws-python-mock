"""A fake implementation of the Vuforia Web Services API.

See
https://developer.vuforia.com/library/vuforia-engine/web-api/vumark-generation-web-api/
"""

import email.utils
import logging
import time
from http import HTTPMethod, HTTPStatus
from typing import TypedDict

import requests
from beartype import beartype
from flask import Flask, Response, request
from pydantic import TypeAdapter
from pydantic_settings import BaseSettings
from werkzeug.exceptions import MethodNotAllowed, NotFound

from mock_vws.database import VuMarkDatabase
from mock_vws.model_target import (
    ModelTargetDataset,
    ModelTargetDatasetType,
    OAuth2ClientCredential,
)
from mock_vws.server_api import (
    VUMARK_PDF,
    VUMARK_PNG,
    VUMARK_SVG,
    InvalidAcceptHeaderError,
    RequestData,
    TargetStatuses,
    TargetStatusNotSuccessError,
    create_model_target_dataset,
    delete_model_target_dataset,
    download_model_target_dataset,
    get_database_matching_server_keys,
    get_model_target_dataset_status,
    run_services_validators,
)
from mock_vws.server_api import (
    ServicesValidatorError as ValidatorError,
)
from mock_vws.server_api import (
    create_oauth2_client_credential as model_target_create_oauth2_credential,
)
from mock_vws.server_api import (
    delete_oauth2_client_credential as model_target_delete_oauth2_credential,
)
from mock_vws.server_api import (
    list_oauth2_client_credentials as model_target_list_oauth2_credentials,
)
from mock_vws.server_api import (
    oauth2_token as model_target_oauth2_token,
)
from mock_vws.server_api import (
    update_oauth2_client_credential_scopes as update_oauth2_scopes,
)

VWS_FLASK_APP = Flask(import_name=__name__, static_folder=None)
VWS_FLASK_APP.config["PROPAGATE_EXCEPTIONS"] = True

# In the Docker deployment the target manager service owns all database and
# target state, and each VWS app instance is otherwise stateless.
# Request rate limit history is deliberately an exception: it is tracked per
# VWS app instance, so it is lost when the app restarts.


_LOGGER = logging.getLogger(name=__name__)


class _OAuth2ClientCredentialBody(TypedDict):
    """An OAuth2 client credential returned by the target manager."""

    client_id: str
    client_secret: str
    scopes: list[str]


_OAUTH2_CLIENT_CREDENTIALS_ADAPTER = TypeAdapter(
    type=list[_OAuth2ClientCredentialBody],
)


@beartype
class VWSSettings(BaseSettings):
    """Settings for the VWS Flask app."""

    target_manager_base_url: str
    processing_time_seconds: float = 2.0
    vws_host: str = ""
    # The base URL which clients use to reach this application.
    # Generated reco counts reports are served from this URL.
    response_delay_seconds: float = 0.0
    model_target_training_allowance_exceeded: bool = False


@beartype
def get_all_vumark_databases() -> set[VuMarkDatabase]:
    """Get all VuMark database objects from the task manager back-end."""
    settings = VWSSettings.model_validate(obj={})
    timeout_seconds = 30
    response = requests.get(
        url=f"{settings.target_manager_base_url}/vumark_databases",
        timeout=timeout_seconds,
    )
    return {
        VuMarkDatabase.from_dict(database_dict=database_dict)
        for database_dict in response.json()
    }


@beartype
def _flask_request_data() -> RequestData:
    """Return the current Flask request as shared request data."""
    return RequestData(
        method=request.method,
        path=request.path,
        headers=dict(request.headers),
        body=request.get_data(parse_form_data=False),
    )


@beartype
class _HTTPModelTargetDatasetStore:
    """Model Target dataset storage backed by the target manager
    service.
    """

    def __init__(self, *, base_url: str) -> None:
        """
        Args:
            base_url: The base URL of the target manager service.
        """
        self._datasets_url = f"{base_url}/model_target_datasets"
        self._credentials_url = f"{base_url}/oauth2_client_credentials"

    @property
    def model_target_datasets(self) -> dict[str, ModelTargetDataset]:
        """All Model Target datasets, keyed by UUID."""
        timeout_seconds = 30
        response = requests.get(
            url=self._datasets_url,
            timeout=timeout_seconds,
        )
        datasets = (
            ModelTargetDataset.from_dict(dataset_dict=dataset_dict)
            for dataset_dict in response.json()
        )
        return {dataset.uuid_: dataset for dataset in datasets}

    def add_model_target_dataset(
        self,
        model_target_dataset: ModelTargetDataset,
    ) -> None:
        """Add a Model Target dataset."""
        timeout_seconds = 30
        _ = requests.post(
            url=self._datasets_url,
            json=model_target_dataset.to_dict(),
            timeout=timeout_seconds,
        )

    def remove_model_target_dataset(self, dataset_uuid: str) -> None:
        """Remove a Model Target dataset."""
        timeout_seconds = 30
        _ = requests.delete(
            url=f"{self._datasets_url}/{dataset_uuid}",
            timeout=timeout_seconds,
        )

    @property
    def oauth2_client_credentials(self) -> dict[str, OAuth2ClientCredential]:
        """All dynamically created OAuth2 client credentials."""
        response = requests.get(url=self._credentials_url, timeout=30)
        credentials = (
            OAuth2ClientCredential(
                client_id=value["client_id"],
                client_secret=value["client_secret"],
                scopes=tuple(value["scopes"]),
            )
            for value in _OAUTH2_CLIENT_CREDENTIALS_ADAPTER.validate_python(
                response.json(),
            )
        )
        return {credential.client_id: credential for credential in credentials}

    def add_oauth2_client_credential(
        self,
        credential: OAuth2ClientCredential,
    ) -> None:
        """Add or replace an OAuth2 client credential."""
        _ = requests.post(
            url=self._credentials_url,
            json={
                "client_id": credential.client_id,
                "client_secret": credential.client_secret,
                "scopes": list(credential.scopes),
            },
            timeout=30,
        )

    def remove_oauth2_client_credential(self, client_id: str) -> None:
        """Remove an OAuth2 client credential."""
        _ = requests.delete(
            url=f"{self._credentials_url}/{client_id}",
            timeout=30,
        )


@beartype
def _model_target_dataset_store() -> _HTTPModelTargetDatasetStore:
    """Return the dataset store backing the Model Target routes."""
    settings = VWSSettings.model_validate(obj={})
    return _HTTPModelTargetDatasetStore(
        base_url=settings.target_manager_base_url,
    )


@beartype
def _to_flask_response(
    api_response: tuple[int, dict[str, str], str | bytes],
) -> Response:
    """Convert a shared API response to a Flask response."""
    status_code, headers, body = api_response
    return Response(response=body, status=status_code, headers=headers)


@VWS_FLASK_APP.before_request
@beartype
def set_terminate_wsgi_input() -> None:
    """We set ``wsgi.input_terminated`` to ``True`` when going through
    ``requests`` in our tests, so that requests have the given ``Content-
    Length`` headers and the given data in ``request.headers`` and
    ``request.data``.

    We do not set this at all when running an application as standalone.
    This is because when running the Flask application, if this is set,
    reading ``request.data`` hangs.

    Therefore, when running the real Flask application, the behavior is not the
    same as the real Vuforia.
    This is documented as a difference in the documentation for this package.
    """
    config = TypeAdapter(type=dict[str, object]).validate_python(
        VWS_FLASK_APP.config,
    )
    terminate_wsgi_input = config.get(
        "VWS_MOCK_TERMINATE_WSGI_INPUT",
    )

    if terminate_wsgi_input is True:
        request.environ["wsgi.input_terminated"] = True


@VWS_FLASK_APP.after_request
@beartype
def add_response_delay(response: Response) -> Response:
    """Add a delay to each response."""
    settings = VWSSettings.model_validate(obj={})
    time.sleep(settings.response_delay_seconds)
    return response


@VWS_FLASK_APP.errorhandler(code_or_exception=ValidatorError)
@beartype
def handle_exceptions(exc: ValidatorError) -> Response:
    """Return the error response associated with the given exception."""
    response = Response(
        status=exc.status_code.value,
        response=exc.response_text,
        headers=exc.headers,
    )

    response.headers.clear()
    response.headers.extend(exc.headers)
    return response


@VWS_FLASK_APP.errorhandler(code_or_exception=HTTPStatus.NOT_FOUND)
@VWS_FLASK_APP.errorhandler(code_or_exception=HTTPStatus.METHOD_NOT_ALLOWED)
@beartype
def handle_unrouted_request(exc: NotFound | MethodNotAllowed) -> Response:
    """Return an empty 404 for requests outside the supported APIs."""
    del exc
    response = Response(status=HTTPStatus.NOT_FOUND, response=b"")
    del response.headers["Content-Type"]
    return response


@VWS_FLASK_APP.route(rule="/oauth2/token", methods=[HTTPMethod.POST])
@beartype
def oauth2_token() -> Response:
    """Obtain an OAuth2 token for the Model Target Web API."""
    return _to_flask_response(
        api_response=model_target_oauth2_token(
            request=_flask_request_data(),
            credential_store=_model_target_dataset_store(),
        ),
    )


@VWS_FLASK_APP.route(
    rule="/oauth2/clientcredentials",
    methods=[HTTPMethod.POST],
)
@beartype
def create_oauth2_client_credential() -> Response:
    """Create an OAuth2 client credential."""
    return _to_flask_response(
        api_response=model_target_create_oauth2_credential(
            request=_flask_request_data(),
            credential_store=_model_target_dataset_store(),
        ),
    )


@VWS_FLASK_APP.route(
    rule="/oauth2/clientcredentials",
    methods=[HTTPMethod.GET],
)
@beartype
def list_oauth2_client_credentials() -> Response:
    """List OAuth2 client credentials."""
    return _to_flask_response(
        api_response=model_target_list_oauth2_credentials(
            request=_flask_request_data(),
            credential_store=_model_target_dataset_store(),
        ),
    )


@VWS_FLASK_APP.route(
    rule="/oauth2/clientcredentials/<string:client_id>/scopes",
    methods=[HTTPMethod.PUT],
)
@beartype
def update_oauth2_client_credential_scopes(client_id: str) -> Response:
    """Update an OAuth2 client credential's scopes."""
    return _to_flask_response(
        api_response=update_oauth2_scopes(
            request=_flask_request_data(),
            credential_store=_model_target_dataset_store(),
            client_id=client_id,
        ),
    )


@VWS_FLASK_APP.route(
    rule="/oauth2/clientcredentials/<string:client_id>",
    methods=[HTTPMethod.DELETE],
)
@beartype
def delete_oauth2_client_credential(client_id: str) -> Response:
    """Delete an OAuth2 client credential."""
    return _to_flask_response(
        api_response=model_target_delete_oauth2_credential(
            request=_flask_request_data(),
            credential_store=_model_target_dataset_store(),
            client_id=client_id,
        ),
    )


@VWS_FLASK_APP.route(
    rule="/modeltargets/datasets",
    methods=[HTTPMethod.POST],
)
@beartype
def create_standard_model_target_dataset() -> Response:
    """Create a standard Model Target dataset."""
    settings = VWSSettings.model_validate(obj={})
    return _to_flask_response(
        api_response=create_model_target_dataset(
            request=_flask_request_data(),
            dataset_store=_model_target_dataset_store(),
            processing_time_seconds=settings.processing_time_seconds,
            dataset_type=ModelTargetDatasetType.STANDARD,
            generation_failure=None,
            generation_warning=None,
            training_allowance_exceeded=(
                settings.model_target_training_allowance_exceeded
            ),
        ),
    )


@VWS_FLASK_APP.route(
    rule="/modeltargets/advancedDatasets",
    methods=[HTTPMethod.POST],
)
@beartype
def create_advanced_model_target_dataset() -> Response:
    """Create an advanced Model Target dataset."""
    settings = VWSSettings.model_validate(obj={})
    return _to_flask_response(
        api_response=create_model_target_dataset(
            request=_flask_request_data(),
            dataset_store=_model_target_dataset_store(),
            processing_time_seconds=settings.processing_time_seconds,
            dataset_type=ModelTargetDatasetType.ADVANCED,
            generation_failure=None,
            generation_warning=None,
            training_allowance_exceeded=(
                settings.model_target_training_allowance_exceeded
            ),
        ),
    )


@VWS_FLASK_APP.route(
    rule="/modeltargets/datasets/<string:dataset_uuid>/status",
    methods=[HTTPMethod.GET],
)
@beartype
def get_standard_model_target_dataset_status(
    dataset_uuid: str,
) -> Response:
    """Return a standard Model Target dataset creation status."""
    return _to_flask_response(
        api_response=get_model_target_dataset_status(
            request=_flask_request_data(),
            dataset_store=_model_target_dataset_store(),
            dataset_uuid=dataset_uuid,
            dataset_type=ModelTargetDatasetType.STANDARD,
        ),
    )


@VWS_FLASK_APP.route(
    rule="/modeltargets/advancedDatasets/<string:dataset_uuid>/status",
    methods=[HTTPMethod.GET],
)
@beartype
def get_advanced_model_target_dataset_status(
    dataset_uuid: str,
) -> Response:
    """Return an advanced Model Target dataset creation status."""
    return _to_flask_response(
        api_response=get_model_target_dataset_status(
            request=_flask_request_data(),
            dataset_store=_model_target_dataset_store(),
            dataset_uuid=dataset_uuid,
            dataset_type=ModelTargetDatasetType.ADVANCED,
        ),
    )


@VWS_FLASK_APP.route(
    rule="/modeltargets/datasets/<string:dataset_uuid>/dataset",
    methods=[HTTPMethod.GET],
)
@beartype
def download_standard_model_target_dataset(
    dataset_uuid: str,
) -> Response:
    """Download a standard Model Target dataset."""
    return _to_flask_response(
        api_response=download_model_target_dataset(
            request=_flask_request_data(),
            dataset_store=_model_target_dataset_store(),
            dataset_uuid=dataset_uuid,
            dataset_type=ModelTargetDatasetType.STANDARD,
        ),
    )


@VWS_FLASK_APP.route(
    rule="/modeltargets/advancedDatasets/<string:dataset_uuid>/dataset",
    methods=[HTTPMethod.GET],
)
@beartype
def download_advanced_model_target_dataset(
    dataset_uuid: str,
) -> Response:
    """Download an advanced Model Target dataset."""
    return _to_flask_response(
        api_response=download_model_target_dataset(
            request=_flask_request_data(),
            dataset_store=_model_target_dataset_store(),
            dataset_uuid=dataset_uuid,
            dataset_type=ModelTargetDatasetType.ADVANCED,
        ),
    )


@VWS_FLASK_APP.route(
    rule="/modeltargets/datasets/<string:dataset_uuid>",
    methods=[HTTPMethod.DELETE],
)
@beartype
def delete_standard_model_target_dataset(dataset_uuid: str) -> Response:
    """Delete a standard Model Target dataset."""
    return _to_flask_response(
        api_response=delete_model_target_dataset(
            request=_flask_request_data(),
            dataset_store=_model_target_dataset_store(),
            dataset_uuid=dataset_uuid,
            dataset_type=ModelTargetDatasetType.STANDARD,
        ),
    )


@VWS_FLASK_APP.route(
    rule="/modeltargets/advancedDatasets/<string:dataset_uuid>",
    methods=[HTTPMethod.DELETE],
)
@beartype
def delete_advanced_model_target_dataset(dataset_uuid: str) -> Response:
    """Delete an advanced Model Target dataset."""
    return _to_flask_response(
        api_response=delete_model_target_dataset(
            request=_flask_request_data(),
            dataset_store=_model_target_dataset_store(),
            dataset_uuid=dataset_uuid,
            dataset_type=ModelTargetDatasetType.ADVANCED,
        ),
    )


@VWS_FLASK_APP.route(
    rule="/targets/<string:target_id>/instances",
    methods=[HTTPMethod.POST],
)
@beartype
def generate_vumark_instance(target_id: str) -> Response:
    """Generate a VuMark instance.

    Fake implementation of
    https://developer.vuforia.com/library/vuforia-engine/web-api/vumark-generation-web-api/#generate-instance
    """
    vumark_databases = get_all_vumark_databases()
    all_databases: list[VuMarkDatabase] = [
        *vumark_databases,
    ]
    _ = run_services_validators(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=all_databases,
    )

    database = get_database_matching_server_keys(
        request_headers=dict(request.headers),
        request_body=request.data,
        request_method=request.method,
        request_path=request.path,
        databases=all_databases,
    )
    target = database.get_vumark_target(target_id=target_id)
    if target.status != TargetStatuses.SUCCESS.value:
        raise TargetStatusNotSuccessError

    accept = request.headers.get(key="Accept", default="")
    valid_accept_types: dict[str, bytes] = {
        "image/png": VUMARK_PNG,
        "image/svg+xml": VUMARK_SVG,
        "application/pdf": VUMARK_PDF,
    }
    if accept not in valid_accept_types:
        raise InvalidAcceptHeaderError

    response_body = valid_accept_types[accept]
    content_type = accept
    date = email.utils.formatdate(timeval=None, localtime=False, usegmt=True)
    headers = {
        "Connection": "keep-alive",
        "Content-Type": content_type,
        "server": "envoy",
        "Date": date,
        "x-envoy-upstream-service-time": "5",
        "strict-transport-security": "max-age=31536000",
        "x-aws-region": "us-east-2, us-west-2",
        "x-content-type-options": "nosniff",
    }
    return Response(
        status=HTTPStatus.OK,
        response=response_body,
        headers=headers,
    )


# Containers execute this process entry point; import-driven tests use its API.
if __name__ == "__main__":  # pragma: no cover
    SETTINGS = VWSSettings.model_validate(obj={})
    VWS_FLASK_APP.run(host=SETTINGS.vws_host)
