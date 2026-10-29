"""Tests for sending various data types."""

from tests.mock_vws.utils import Endpoint


def test_text(endpoint: Endpoint) -> None:
    """It is possible to send strings to VWS endpoints."""
    assert isinstance(endpoint.data, bytes)
    new_endpoint = Endpoint(
        base_url=endpoint.base_url,
        path_url=endpoint.path_url,
        method=endpoint.method,
        headers=endpoint.headers,
        data=endpoint.data.decode(encoding="utf-8"),
        successful_headers_result_code=endpoint.successful_headers_result_code,
        successful_headers_status_code=endpoint.successful_headers_status_code,
        access_key=endpoint.access_key,
        secret_key=endpoint.secret_key,
    )
    response = new_endpoint.send()
    assert response.status_code == endpoint.successful_headers_status_code
