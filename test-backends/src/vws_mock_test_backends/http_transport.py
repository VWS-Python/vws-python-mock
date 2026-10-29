"""HTTP transport for unmatched contract-suite requests."""

from http import HTTPMethod

import requests
from beartype import beartype

from vws_mock_contract_tests.utils.unrouted_requests import (
    UnroutedRequests,
    UnroutedResponse,
)


@beartype
def http_unrouted_requests(
    *, base_vws_url: str, returns_response: bool
) -> UnroutedRequests:
    """Bind unmatched requests to an endpoint and its response policy."""

    @beartype
    def send_http_request(
        *,
        method: HTTPMethod,
        request_path: str,
        headers: dict[str, str],
    ) -> UnroutedResponse | None:
        """Send an unmatched request to the configured VWS URL."""
        try:
            response = requests.request(
                method=method,
                url=base_vws_url + request_path,
                headers=headers,
                timeout=30,
            )
        except requests.exceptions.ConnectionError:
            return None

        return UnroutedResponse(
            status_code=response.status_code,
            body=response.content,
            content_type=response.headers.get("Content-Type"),
            content_encoding=response.headers.get("Content-Encoding"),
            upstream_service_time=response.headers.get(
                "x-envoy-upstream-service-time",
            ),
        )

    return UnroutedRequests(
        send=send_http_request,
        returns_response=returns_response,
    )
