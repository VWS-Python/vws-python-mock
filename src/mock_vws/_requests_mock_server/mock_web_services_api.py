"""A fake implementation of the Vuforia Web Services API.

See
https://developer.vuforia.com/library/vuforia-engine/web-api/vumark-generation-web-api/
"""

import email.utils
import uuid
from collections.abc import Callable, Iterable, Mapping
from http import HTTPMethod, HTTPStatus

from beartype import BeartypeConf, beartype

from mock_vws._constants import (
    VUMARK_PDF,
    VUMARK_PNG,
    VUMARK_SVG,
    TargetStatuses,
)
from mock_vws._mock_common import (
    RequestData,
    Route,
    RouteDefinition,
    json_dump,
)
from mock_vws._model_target_web_api import (
    create_model_target_dataset,
    create_oauth2_client_credential,
    delete_model_target_dataset,
    delete_oauth2_client_credential,
    download_model_target_dataset,
    get_model_target_dataset_status,
    list_oauth2_client_credentials,
    oauth2_token,
    update_oauth2_client_credential_scopes,
)
from mock_vws._services_validators import run_services_validators
from mock_vws._services_validators.exceptions import (
    InvalidAcceptHeaderError,
    TargetStatusNotSuccessError,
    ValidatorError,
)
from mock_vws.database import VuMarkDatabase
from mock_vws.model_target import (
    ModelTargetDatasetType,
    ModelTargetFailureResponse,
    ModelTargetGenerationFailure,
    ModelTargetGenerationWarning,
    ModelTargetRequest,
)
from mock_vws.target_manager import TargetManager
from mock_vws.vumark import VuMarkGenerationFailure

_TARGET_ID_PATTERN = "[A-Za-z0-9]+"
_MODEL_TARGET_DATASET_UUID_PATTERN = "[A-Za-z0-9-]+"


_ResponseType = tuple[int, Mapping[str, str], str | bytes]
type _RouteMethod = Callable[
    ["MockVuforiaWebServicesAPI", RequestData],
    _ResponseType,
]
_ROUTES = set[RouteDefinition["MockVuforiaWebServicesAPI"]]()


@beartype
def route(
    *,
    path_pattern: str,
    http_methods: Iterable[HTTPMethod],
) -> Callable[[_RouteMethod], _RouteMethod]:
    """Register a decorated method so that it can be recognized as a route.

    Args:
        path_pattern: The end part of a URL pattern. E.g. `/targets` or
          `/targets/.+`.
        http_methods: HTTP methods that map to the route function.

    Returns:
        A decorator which takes methods and makes them recognizable as routes.
    """

    @beartype
    def decorator(
        method: _RouteMethod,
    ) -> _RouteMethod:
        """Register a decorated method so that it can be recognized as a
        route.

        Returns:
            The given `method` with multiple changes, including added
            validators.
        """
        new_route = RouteDefinition(
            handler=method,
            path_pattern=path_pattern,
            http_methods=frozenset(http_methods),
        )
        _ROUTES.add(new_route)

        return method

    return decorator


# This single facade intentionally exposes the complete mock route surface;
# splitting it would separate one cohesive public API.
@beartype(conf=BeartypeConf(is_pep484_tower=True))
class MockVuforiaWebServicesAPI:
    """A fake implementation of the Vuforia Web Services API."""

    def __init__(
        self,
        *,
        target_manager: TargetManager,
        processing_time_seconds: float,
        model_target_generation_failure: ModelTargetGenerationFailure | None,
        model_target_failure_response: ModelTargetFailureResponse | None,
        model_target_generation_warning: ModelTargetGenerationWarning | None,
        model_target_training_allowance_exceeded: bool,
        vumark_generation_failure: VuMarkGenerationFailure | None,
    ) -> None:
        """Create handlers for Model Targets, OAuth2, and VuMark
        generation.
        """
        self._target_manager = target_manager
        self.routes: set[Route] = {route.bind(api=self) for route in _ROUTES}
        self._processing_time_seconds = processing_time_seconds
        self._model_target_generation_failure = model_target_generation_failure
        self._model_target_failure_response = model_target_failure_response
        self._model_target_generation_warning = model_target_generation_warning
        self._model_target_training_allowance_exceeded = (
            model_target_training_allowance_exceeded
        )
        self._vumark_generation_failure = vumark_generation_failure

    def _configured_model_target_failure(
        self,
        request_phase: ModelTargetRequest,
    ) -> _ResponseType | None:
        """Return the configured failure for a Model Target request
        phase.
        """
        failure = self._model_target_failure_response
        if failure is None or request_phase not in failure.requests:
            return None
        return failure.status_code, failure.headers, failure.body

    @route(path_pattern="/oauth2/token", http_methods={HTTPMethod.POST})
    def oauth2_token(
        self,
        request: RequestData,
    ) -> _ResponseType:
        """Obtain an OAuth2 token for the Model Target Web API."""
        return oauth2_token(
            request=request,
            credential_store=self._target_manager,
        )

    @route(
        path_pattern="/oauth2/clientcredentials",
        http_methods={HTTPMethod.POST},
    )
    def create_oauth2_client_credential(
        self,
        request: RequestData,
    ) -> _ResponseType:
        """Create an OAuth2 client credential."""
        return create_oauth2_client_credential(
            request=request,
            credential_store=self._target_manager,
        )

    @route(
        path_pattern="/oauth2/clientcredentials",
        http_methods={HTTPMethod.GET},
    )
    def list_oauth2_client_credentials(
        self,
        request: RequestData,
    ) -> _ResponseType:
        """List OAuth2 client credentials."""
        return list_oauth2_client_credentials(
            request=request,
            credential_store=self._target_manager,
        )

    @route(
        path_pattern=("/oauth2/clientcredentials/(?P<client_id>[^/]+)/scopes"),
        http_methods={HTTPMethod.PUT},
    )
    def update_oauth2_client_credential_scopes(
        self,
        request: RequestData,
    ) -> _ResponseType:
        """Update an OAuth2 client credential's scopes."""
        client_id = request.path.split(sep="/")[-2]
        return update_oauth2_client_credential_scopes(
            request=request,
            credential_store=self._target_manager,
            client_id=client_id,
        )

    @route(
        path_pattern="/oauth2/clientcredentials/(?P<client_id>[^/]+)",
        http_methods={HTTPMethod.DELETE},
    )
    def delete_oauth2_client_credential(
        self,
        request: RequestData,
    ) -> _ResponseType:
        """Delete an OAuth2 client credential."""
        client_id = request.path.rsplit(sep="/", maxsplit=1)[-1]
        return delete_oauth2_client_credential(
            request=request,
            credential_store=self._target_manager,
            client_id=client_id,
        )

    @route(
        path_pattern="/modeltargets/datasets",
        http_methods={HTTPMethod.POST},
    )
    def create_standard_model_target_dataset(
        self,
        request: RequestData,
    ) -> _ResponseType:
        """Create a standard Model Target dataset."""
        failure = self._configured_model_target_failure(
            request_phase=ModelTargetRequest.CREATE,
        )
        if failure is not None:
            return failure
        return create_model_target_dataset(
            request=request,
            dataset_store=self._target_manager,
            processing_time_seconds=self._processing_time_seconds,
            dataset_type=ModelTargetDatasetType.STANDARD,
            generation_failure=self._model_target_generation_failure,
            generation_warning=self._model_target_generation_warning,
            training_allowance_exceeded=(
                self._model_target_training_allowance_exceeded
            ),
        )

    @route(
        path_pattern="/modeltargets/advancedDatasets",
        http_methods={HTTPMethod.POST},
    )
    def create_advanced_model_target_dataset(
        self,
        request: RequestData,
    ) -> _ResponseType:
        """Create an advanced Model Target dataset."""
        failure = self._configured_model_target_failure(
            request_phase=ModelTargetRequest.CREATE,
        )
        if failure is not None:
            return failure
        return create_model_target_dataset(
            request=request,
            dataset_store=self._target_manager,
            processing_time_seconds=self._processing_time_seconds,
            dataset_type=ModelTargetDatasetType.ADVANCED,
            generation_failure=self._model_target_generation_failure,
            generation_warning=self._model_target_generation_warning,
            training_allowance_exceeded=(
                self._model_target_training_allowance_exceeded
            ),
        )

    @route(
        path_pattern=(
            "/modeltargets/datasets/"
            f"{_MODEL_TARGET_DATASET_UUID_PATTERN}/status"
        ),
        http_methods={HTTPMethod.GET},
    )
    def get_standard_model_target_dataset_status(
        self,
        request: RequestData,
    ) -> _ResponseType:
        """Return a standard Model Target dataset creation status."""
        failure = self._configured_model_target_failure(
            request_phase=ModelTargetRequest.STATUS,
        )
        if failure is not None:
            return failure
        dataset_uuid = request.path.split(sep="/")[-2]
        return get_model_target_dataset_status(
            request=request,
            dataset_store=self._target_manager,
            dataset_uuid=dataset_uuid,
            dataset_type=ModelTargetDatasetType.STANDARD,
        )

    @route(
        path_pattern=(
            "/modeltargets/advancedDatasets/"
            f"{_MODEL_TARGET_DATASET_UUID_PATTERN}/status"
        ),
        http_methods={HTTPMethod.GET},
    )
    def get_advanced_model_target_dataset_status(
        self,
        request: RequestData,
    ) -> _ResponseType:
        """Return an advanced Model Target dataset creation status."""
        failure = self._configured_model_target_failure(
            request_phase=ModelTargetRequest.STATUS,
        )
        if failure is not None:
            return failure
        dataset_uuid = request.path.split(sep="/")[-2]
        return get_model_target_dataset_status(
            request=request,
            dataset_store=self._target_manager,
            dataset_uuid=dataset_uuid,
            dataset_type=ModelTargetDatasetType.ADVANCED,
        )

    @route(
        path_pattern=(
            "/modeltargets/datasets/"
            f"{_MODEL_TARGET_DATASET_UUID_PATTERN}/dataset"
        ),
        http_methods={HTTPMethod.GET},
    )
    def download_standard_model_target_dataset(
        self,
        request: RequestData,
    ) -> _ResponseType:
        """Download a standard Model Target dataset."""
        failure = self._configured_model_target_failure(
            request_phase=ModelTargetRequest.DOWNLOAD,
        )
        if failure is not None:
            return failure
        dataset_uuid = request.path.split(sep="/")[-2]
        return download_model_target_dataset(
            request=request,
            dataset_store=self._target_manager,
            dataset_uuid=dataset_uuid,
            dataset_type=ModelTargetDatasetType.STANDARD,
        )

    @route(
        path_pattern=(
            "/modeltargets/advancedDatasets/"
            f"{_MODEL_TARGET_DATASET_UUID_PATTERN}/dataset"
        ),
        http_methods={HTTPMethod.GET},
    )
    def download_advanced_model_target_dataset(
        self,
        request: RequestData,
    ) -> _ResponseType:
        """Download an advanced Model Target dataset."""
        failure = self._configured_model_target_failure(
            request_phase=ModelTargetRequest.DOWNLOAD,
        )
        if failure is not None:
            return failure
        dataset_uuid = request.path.split(sep="/")[-2]
        return download_model_target_dataset(
            request=request,
            dataset_store=self._target_manager,
            dataset_uuid=dataset_uuid,
            dataset_type=ModelTargetDatasetType.ADVANCED,
        )

    @route(
        path_pattern=(
            f"/modeltargets/datasets/{_MODEL_TARGET_DATASET_UUID_PATTERN}"
        ),
        http_methods={HTTPMethod.DELETE},
    )
    def delete_standard_model_target_dataset(
        self,
        request: RequestData,
    ) -> _ResponseType:
        """Delete a standard Model Target dataset."""
        failure = self._configured_model_target_failure(
            request_phase=ModelTargetRequest.DELETE,
        )
        if failure is not None:
            return failure
        dataset_uuid = request.path.split(sep="/")[-1]
        return delete_model_target_dataset(
            request=request,
            dataset_store=self._target_manager,
            dataset_uuid=dataset_uuid,
            dataset_type=ModelTargetDatasetType.STANDARD,
        )

    @route(
        path_pattern=(
            "/modeltargets/advancedDatasets/"
            f"{_MODEL_TARGET_DATASET_UUID_PATTERN}"
        ),
        http_methods={HTTPMethod.DELETE},
    )
    def delete_advanced_model_target_dataset(
        self,
        request: RequestData,
    ) -> _ResponseType:
        """Delete an advanced Model Target dataset."""
        failure = self._configured_model_target_failure(
            request_phase=ModelTargetRequest.DELETE,
        )
        if failure is not None:
            return failure
        dataset_uuid = request.path.split(sep="/")[-1]
        return delete_model_target_dataset(
            request=request,
            dataset_store=self._target_manager,
            dataset_uuid=dataset_uuid,
            dataset_type=ModelTargetDatasetType.ADVANCED,
        )

    @route(
        path_pattern=f"/targets/{_TARGET_ID_PATTERN}/instances",
        http_methods={HTTPMethod.POST},
    )
    def generate_vumark_instance(self, request: RequestData) -> _ResponseType:
        """Generate a VuMark instance."""
        if self._vumark_generation_failure is not None:
            body_json = json_dump(
                body={
                    "transaction_id": uuid.uuid4().hex,
                    "result_code": self._vumark_generation_failure.value,
                }
            )
            date = email.utils.formatdate(
                timeval=None,
                localtime=False,
                usegmt=True,
            )
            return (
                self._vumark_generation_failure.status_code,
                {
                    "Content-Length": str(object=len(body_json)),
                    "Content-Type": "application/json",
                    "Date": date,
                },
                body_json,
            )

        valid_accept_types: dict[str, bytes] = {
            "image/png": VUMARK_PNG,
            "image/svg+xml": VUMARK_SVG,
            "application/pdf": VUMARK_PDF,
        }
        try:
            all_databases: list[VuMarkDatabase] = [
                *self._target_manager.vumark_databases,
            ]
            database = run_services_validators(
                request_headers=request.headers,
                request_body=request.body,
                request_method=request.method,
                request_path=request.path,
                databases=all_databases,
            )
            target_id = request.path.split(sep="/")[-2]
            target = database.get_vumark_target(target_id=target_id)
            if target.status != TargetStatuses.SUCCESS.value:
                raise TargetStatusNotSuccessError

            accept = dict(request.headers).get("Accept", "")
            if accept not in valid_accept_types:
                raise InvalidAcceptHeaderError
        except ValidatorError as exc:
            return exc.status_code, exc.headers, exc.response_text

        response_body = valid_accept_types[accept]
        content_type = accept
        date = email.utils.formatdate(
            timeval=None,
            localtime=False,
            usegmt=True,
        )
        headers = {
            "Connection": "keep-alive",
            "Content-Type": content_type,
            "Date": date,
            "server": "envoy",
            "x-envoy-upstream-service-time": "5",
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }
        return HTTPStatus.OK, headers, response_body
