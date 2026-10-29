"""Shared API fixtures supplied independently of backend adapters."""

import pytest

from vws_mock_contract_tests.utils import Endpoint, ModelTargetEndpoint

# The number of targets to add before giving up on getting one which
# processes with a 'success' status.
_TARGET_SUCCESS_ATTEMPTS = 3


@pytest.fixture(params=["vumark_generate_instance"])
def endpoint(*, request: pytest.FixtureRequest) -> Endpoint:
    """
    Return details of an endpoint for the Target API or the Query
    API.

    The reco counts report download endpoint is not included because it
    deliberately takes no authorization, standing in for a presigned URL, so
    the cross-cutting ``Authorization`` and ``Date`` header concerns do not
    apply to it.
    """
    fixture_name = request.param
    assert isinstance(fixture_name, str)
    endpoint_fixture = request.getfixturevalue(argname=fixture_name)
    assert isinstance(endpoint_fixture, Endpoint)
    return endpoint_fixture


@pytest.fixture(
    params=[
        "create_standard_dataset",
        "create_advanced_dataset",
        "standard_dataset_status",
        "advanced_dataset_status",
        "download_standard_dataset",
        "download_advanced_dataset",
        "delete_standard_dataset",
        "delete_advanced_dataset",
    ],
)
def model_target_endpoint(
    *,
    request: pytest.FixtureRequest,
) -> ModelTargetEndpoint:
    """Return details of an endpoint for the Model Target Web API.

    The OAuth2 token endpoint is not included because it takes HTTP Basic
    credentials rather than a bearer token, so the cross-cutting bearer
    token concerns do not apply to it.
    """
    fixture_name = request.param
    assert isinstance(fixture_name, str)
    endpoint_fixture = request.getfixturevalue(argname=fixture_name)
    assert isinstance(endpoint_fixture, ModelTargetEndpoint)
    return endpoint_fixture
