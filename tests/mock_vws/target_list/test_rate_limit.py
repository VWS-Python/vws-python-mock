"""Tests for the request rate limit of the target list endpoint."""

from http import HTTPMethod, HTTPStatus

from vws.response import Response
from vws_auth_tools import authorization_header, rfc_1123_date

from tests.mock_vws.fixtures.credentials import CloudDatabaseCredentials
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import assert_vws_too_many_requests
from tests.mock_vws.utils.backend_capabilities import BackendCapabilities

_REQUESTS_PER_MINUTE = 2


def test_two_requests_per_minute(
    *,
    base_vws_url: str,
    backend_capabilities: BackendCapabilities,
    rate_limited_database: CloudDatabaseCredentials,
) -> None:
    """A third ``GET /targets`` request within a minute is rate
    limited,
    with the empty response which Envoy gives.

    Real Vuforia's window is a fixed clock minute, and the fixture which
    empties the database before each test has already listed the
    targets, so the real backend may reject the first, second or third
    request. The mocks use a rolling window on a fresh database, so they
    reject exactly the third.
    """
    responses: list[Response] = []
    # Real Vuforia's fixed window means the rejection may come on any
    # of the first three requests, so requests are sent until one is
    # rejected, with a cap well above the limit.
    while True:
        date = rfc_1123_date()
        authorization = authorization_header(
            access_key=rate_limited_database.server_access_key,
            secret_key=rate_limited_database.server_secret_key,
            method=HTTPMethod.GET,
            content=b"",
            content_type="",
            date=date,
            request_path="/targets",
        )
        endpoint = Endpoint(
            base_url=base_vws_url,
            path_url="/targets",
            method=HTTPMethod.GET,
            headers={"Authorization": authorization, "Date": date},
            data=b"",
            successful_headers_result_code="Success",
            successful_headers_status_code=HTTPStatus.OK,
            access_key=rate_limited_database.server_access_key,
            secret_key=rate_limited_database.server_secret_key,
        )
        response = endpoint.send()
        responses.append(response)
        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            break
        assert len(responses) <= _REQUESTS_PER_MINUTE + 2

    status_codes = [response.status_code for response in responses]
    if backend_capabilities.rolling_rate_limit_window:
        assert status_codes == [
            *[HTTPStatus.OK] * _REQUESTS_PER_MINUTE,
            HTTPStatus.TOO_MANY_REQUESTS,
        ]
    assert status_codes[-1] == HTTPStatus.TOO_MANY_REQUESTS
    assert status_codes.count(HTTPStatus.OK) <= _REQUESTS_PER_MINUTE
    assert_vws_too_many_requests(response=responses[-1])
