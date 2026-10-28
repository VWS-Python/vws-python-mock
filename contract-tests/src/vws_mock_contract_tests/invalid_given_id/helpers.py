"""Shared helpers for invalid given id tests."""

from http import HTTPMethod

from beartype import beartype
from vws_auth_tools import authorization_header, rfc_1123_date

from vws_mock_contract_tests.fixtures.credentials import (
    CloudDatabaseCredentials,
)
from vws_mock_contract_tests.utils.unrouted_requests import (
    SendUnroutedRequest,
    UnroutedResponse,
)


@beartype
def send_unrouted_request(
    *,
    send: SendUnroutedRequest,
    vuforia_database: CloudDatabaseCredentials,
    method: HTTPMethod,
    request_path: str,
) -> UnroutedResponse | None:
    """Send a signed request which no route serves and return the response.

    ``None`` is returned when the backend refuses the connection rather than
    returning a response.
    """
    date = rfc_1123_date()
    headers = {
        "Authorization": authorization_header(
            access_key=vuforia_database.server_access_key,
            secret_key=vuforia_database.server_secret_key,
            method=method,
            content=b"",
            content_type="",
            date=date,
            request_path=request_path,
        ),
        "Date": date,
    }

    return send(
        method=method,
        request_path=request_path,
        headers=headers,
    )
