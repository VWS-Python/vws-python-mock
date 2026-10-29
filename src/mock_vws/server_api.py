"""Supported core operations for VWS and VWQ server implementations.

Server adapters supply HTTP request data and database state to these
operations, then translate their results or validation errors into HTTP
responses. Core owns validation order, matching and response construction.
The operations have no dependency on Flask or a running server.
"""

from mock_vws._constants import (
    VUMARK_PDF,
    VUMARK_PNG,
    VUMARK_SVG,
    ResultCodes,
    TargetStatuses,
)
from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._mock_common import RequestData, json_dump
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
    FailError,
    InvalidAcceptHeaderError,
    TargetStatusNotSuccessError,
)
from mock_vws._services_validators.exceptions import (
    ValidatorError as ServicesValidatorError,
)

__all__ = [
    "VUMARK_PDF",
    "VUMARK_PNG",
    "VUMARK_SVG",
    "FailError",
    "InvalidAcceptHeaderError",
    "RequestData",
    "ResultCodes",
    "ServicesValidatorError",
    "TargetStatusNotSuccessError",
    "TargetStatuses",
    "create_model_target_dataset",
    "create_oauth2_client_credential",
    "delete_model_target_dataset",
    "delete_oauth2_client_credential",
    "download_model_target_dataset",
    "get_database_matching_server_keys",
    "get_model_target_dataset_status",
    "json_dump",
    "list_oauth2_client_credentials",
    "oauth2_token",
    "run_services_validators",
    "update_oauth2_client_credential_scopes",
]
