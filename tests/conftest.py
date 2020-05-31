"""
Configuration, plugins and fixtures for `pytest`.
"""

import base64
import binascii
import io
import time
from typing import List, Tuple

import pytest
from _pytest.fixtures import SubRequest

from mock_vws.database import VuforiaDatabase
from tests.mock_vws.utils import (
    Endpoint,
    UnexpectedEmptyInternalServerError,
    add_target_to_vws,
)

pytest_plugins = [
    'tests.mock_vws.fixtures.prepared_requests',
    'tests.mock_vws.fixtures.credentials',
    'tests.mock_vws.fixtures.vuforia_backends',
]


def is_internal_server_error(
    err: Tuple,
    *args: Tuple,
) -> bool:  # pragma: no cover
    """
    Return whether the error is an ``UnexpectedEmptyInternalServerError``, so
    that we can retry a test if it is.
    """
    assert args
    is_unexpected_server_error = bool(
        err[0] == UnexpectedEmptyInternalServerError,
    )
    if is_unexpected_server_error:
        # We have seen this error happen multiple times when the server is hit
        # in quick succession.
        # We therefore have a delay, to give the server time to recover.
        #
        # The delay length is arbitrary.
        time.sleep(30)
    return is_unexpected_server_error


def pytest_collection_modifyitems(items: List[pytest.Function]) -> None:
    """
    Add a marker to each test which will retry the test if an
    ``UnexpectedEmptyInternalServerError`` is raised.
    """
    retry_marker = pytest.mark.flaky(
        max_runs=5,
        rerun_filter=is_internal_server_error,
    )
    for item in items:
        item.add_marker(retry_marker)


@pytest.fixture()
def target_id(
    image_file_success_state_low_rating: io.BytesIO,
    vuforia_database: VuforiaDatabase,
) -> str:
    """
    Return the target ID of a target in the database.

    The target is one which will have a 'success' status when processed.
    """
    image_data = image_file_success_state_low_rating.read()
    image_data_encoded = base64.b64encode(image_data).decode('ascii')

    data = {
        'name': 'example',
        'width': 1,
        'image': image_data_encoded,
    }

    response = add_target_to_vws(
        vuforia_database=vuforia_database,
        data=data,
        content_type='application/json',
    )

    new_target_id: str = response.json()['target_id']
    return new_target_id


@pytest.fixture(
    params=[
        '_add_target',
        '_database_summary',
        '_delete_target',
        '_get_duplicates',
        '_get_target',
        '_target_list',
        '_target_summary',
        '_update_target',
        '_query',
    ],
)
def endpoint(request: SubRequest) -> Endpoint:
    """
    Return details of an endpoint for the Target API or the Query API.
    """
    endpoint_fixture: Endpoint = request.getfixturevalue(request.param)
    return endpoint_fixture


@pytest.fixture(
    params=[
        pytest.param(
            'abcde',
            id='Length is one more than a multiple of four.',
        ),
        pytest.param(
            # We choose XN because it is different when decoded then encoded:
            #
            #   print(base64.b64encode(base64.b64decode('XN==')))
            #
            # prints ``XA==``.
            'XN',
            id='Length is two more than a multiple of four.',
        ),
        pytest.param(
            'XNA',
            id='Length is three more than a multiple of four.',
        ),
    ],
)
def not_base64_encoded_processable(request: SubRequest) -> str:
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
            id='Includes a character which is not a base64 digit.',
        ),
        pytest.param('"', id='Not a base64 character.'),
    ],
)
def not_base64_encoded_not_processable(request: SubRequest) -> str:
    """
    Return a string which is not decodable as base64 data, and Vuforia will
    return an ``UNPROCESSABLE_ENTITY`` response when this is given.
    """
    not_base64_encoded_string: str = request.param

    with pytest.raises(binascii.Error):
        base64.b64decode(not_base64_encoded_string, validate=True)

    return not_base64_encoded_string
