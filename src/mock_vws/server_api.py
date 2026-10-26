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
from mock_vws._matching import matching_targets
from mock_vws._mock_common import RequestData, json_dump, sorted_targets
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
from mock_vws._query_tools import get_query_match_response_text
from mock_vws._query_validators import ValidatedQuery, run_query_validators
from mock_vws._query_validators.exceptions import (
    ValidatorError as QueryValidatorError,
)
from mock_vws._reco_counts_web_api import (
    create_reco_counts_report,
    download_reco_counts_report,
)
from mock_vws._services_validators import run_services_validators
from mock_vws._services_validators.exceptions import (
    FailError,
    InvalidAcceptHeaderError,
    InvalidTargetTypeError,
    TargetStatusNotSuccessError,
    TargetStatusProcessingError,
)
from mock_vws._services_validators.exceptions import (
    ValidatorError as ServicesValidatorError,
)
from mock_vws._services_validators.request_rate_limiter import (
    RequestRateLimiter,
)

__all__ = [
    "VUMARK_PDF",
    "VUMARK_PNG",
    "VUMARK_SVG",
    "FailError",
    "InvalidAcceptHeaderError",
    "InvalidTargetTypeError",
    "QueryValidatorError",
    "RequestData",
    "RequestRateLimiter",
    "ResultCodes",
    "ServicesValidatorError",
    "TargetStatusNotSuccessError",
    "TargetStatusProcessingError",
    "TargetStatuses",
    "ValidatedQuery",
    "create_model_target_dataset",
    "create_oauth2_client_credential",
    "create_reco_counts_report",
    "delete_model_target_dataset",
    "delete_oauth2_client_credential",
    "download_model_target_dataset",
    "download_reco_counts_report",
    "get_database_matching_server_keys",
    "get_model_target_dataset_status",
    "get_query_match_response_text",
    "json_dump",
    "list_oauth2_client_credentials",
    "matching_targets",
    "oauth2_token",
    "run_query_validators",
    "run_services_validators",
    "sorted_targets",
    "update_oauth2_client_credential_scopes",
]
