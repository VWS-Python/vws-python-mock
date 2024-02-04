"""
Configuration, plugins and fixtures for `pytest`.
"""
from __future__ import annotations

import base64
import binascii
import uuid
from typing import TYPE_CHECKING

import pytest
from vws import VWS, CloudRecoService

if TYPE_CHECKING:
    import io

    from mock_vws.database import VuforiaDatabase

    from tests.mock_vws.utils import Endpoint

pytest_plugins = [
    "tests.mock_vws.fixtures.prepared_requests",
    "tests.mock_vws.fixtures.credentials",
    "tests.mock_vws.fixtures.vuforia_backends",
]


@pytest.fixture(name="vws_client")
def fixture_vws_client(vuforia_database: VuforiaDatabase) -> VWS:
    """
    A VWS client for an active VWS database.
    """
    return VWS(
        server_access_key=vuforia_database.server_access_key,
        server_secret_key=vuforia_database.server_secret_key,
    )


@pytest.fixture()
def cloud_reco_client(vuforia_database: VuforiaDatabase) -> CloudRecoService:
    """
    A query client for an active VWS database.
    """
    return CloudRecoService(
        client_access_key=vuforia_database.client_access_key,
        client_secret_key=vuforia_database.client_secret_key,
    )


@pytest.fixture(name="inactive_vws_client")
def fixture_inactive_vws_client(inactive_database: VuforiaDatabase) -> VWS:
    """
    A client for an inactive VWS database.
    """
    return VWS(
        server_access_key=inactive_database.server_access_key,
        server_secret_key=inactive_database.server_secret_key,
    )


@pytest.fixture()
def target_id(
    image_file_success_state_low_rating: io.BytesIO,
    vws_client: VWS,
) -> str:
    """
    Return the target ID of a target in the database.

    The target is one which will have a 'success' status when processed.
    """
    return vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_file_success_state_low_rating,
        active_flag=True,
        application_metadata=None,
    )


@pytest.fixture(
    params=[
        "add_target",
        "database_summary",
        "delete_target",
        "get_duplicates",
        "get_target",
        "target_list",
        "target_summary",
        "update_target",
        "query",
    ],
)
def endpoint(request: pytest.FixtureRequest) -> Endpoint:
    """
    Return details of an endpoint for the Target API or the Query API.
    """
    endpoint_fixture: Endpoint = request.getfixturevalue(request.param)
    return endpoint_fixture


@pytest.fixture(
    params=[
        pytest.param(
            "abcde",
            id="Length is one more than a multiple of four.",
        ),
        pytest.param(
            # We choose XN because it is different when decoded then encoded:
            #
            #
            # prints ``XA==``.
            "XN",
            id="Length is two more than a multiple of four.",
        ),
        pytest.param(
            "XNA",
            id="Length is three more than a multiple of four.",
        ),
    ],
)
def not_base64_encoded_processable(request: pytest.FixtureRequest) -> str:
    """
    Return a string which is not decodable as base64 data, but Vuforia will
    respond as if this is valid base64 data.
    ``UNPROCESSABLE_ENTITY`` when this is given.
    """
    not_base64_encoded_string: str = request.param

    with pytest.raises(binascii.Error):
        base64.b64decode(not_base64_encoded_string, validate=True)

    return not_base64_encoded_string


@pytest.fixture(
    params=[
        pytest.param(
            'aaa"',
            id="Includes a character which is not a base64 digit.",
        ),
        pytest.param('"', id="Not a base64 character."),
    ],
)
def not_base64_encoded_not_processable(request: pytest.FixtureRequest) -> str:
    """
    Return a string which is not decodable as base64 data, and Vuforia will
    return an ``UNPROCESSABLE_ENTITY`` response when this is given.
    """
    not_base64_encoded_string: str = request.param

    with pytest.raises(binascii.Error):
        base64.b64decode(not_base64_encoded_string, validate=True)

    return not_base64_encoded_string
