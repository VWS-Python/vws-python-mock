"""Tests for the ``Content-Length`` header on every Model Target
endpoint.

These mirror the cross-cutting tests which the ``endpoint`` fixture
supports for the VWS and Query APIs.

A ``Content-Length`` header which is too large is not covered, for the
same reason as it is not covered for the VWS API: real Vuforia waits
for the body it was promised before timing out, which takes too long
to run in a test.
"""

import dataclasses
from http import HTTPMethod, HTTPStatus

from tests.mock_vws.model_target_web_api.assertions import (
    assert_model_target_error,
)
from tests.mock_vws.model_target_web_api.authentication import (
    VWS_HOST,
)
from tests.mock_vws.model_target_web_api.requests.helpers import (
    assert_load_balancer_bad_request,
)
from tests.mock_vws.utils import ModelTargetEndpoint


def test_not_integer(
    *,
    model_target_endpoint: ModelTargetEndpoint,
) -> None:
    """A ``Content-Length`` header which is not an integer is rejected
    by the load balancer in front of Vuforia, before any bearer token
    is looked at.
    """
    new_endpoint = dataclasses.replace(
        model_target_endpoint,
        headers={
            **model_target_endpoint.headers,
            "Content-Length": "0.4",
        },
    )

    response = new_endpoint.send()

    assert_load_balancer_bad_request(response=response)


def test_not_integer_oauth2_token() -> None:
    """The OAuth2 token endpoint is behind the same load balancer.

    It is not in the ``model_target_endpoint`` fixture because it takes
    HTTP Basic credentials rather than a bearer token.
    """
    endpoint = ModelTargetEndpoint(
        base_url=VWS_HOST,
        path_url="/oauth2/token",
        method=HTTPMethod.POST,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": "0.4",
        },
        data=b"grant_type=client_credentials",
        takes_json_body=False,
    )

    response = endpoint.send()

    assert_load_balancer_bad_request(response=response)


def test_too_small(
    *,
    model_target_endpoint: ModelTargetEndpoint,
) -> None:
    """A ``Content-Length`` header which is too small truncates the
    body, and the request is still rejected for having no bearer
    token.

    The Model Target Web API does not sign the request body, so unlike
    the VWS API it has no reason to notice the truncation before it
    looks at the ``Authorization`` header.
    """
    if not model_target_endpoint.takes_json_body:
        return

    content_length = len(model_target_endpoint.data) - 1
    new_endpoint = dataclasses.replace(
        model_target_endpoint,
        headers={
            **model_target_endpoint.headers,
            "Content-Length": str(object=content_length),
        },
    )

    response = new_endpoint.send()

    assert_model_target_error(
        response=response,
        status_code=HTTPStatus.UNAUTHORIZED,
        code="401",
        message="no Bearer token",
        target="jwt",
    )
