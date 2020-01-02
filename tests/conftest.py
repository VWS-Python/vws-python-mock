"""
Configuration, plugins and fixtures for `pytest`.
"""

import base64
import binascii
import io
import json
import logging
import os
from typing import Generator

import pytest
from _pytest.fixtures import SubRequest
from requests import codes

from mock_vws import MockVWS
from mock_vws._constants import ResultCodes
from mock_vws.database import VuforiaDatabase
from mock_vws.states import States
from tests.mock_vws.utils import (
    Endpoint,
    add_target_to_vws,
    delete_target,
    list_targets,
    update_target,
    wait_for_target_processed,
)
from tests.mock_vws.utils.assertions import assert_vws_response

pytest_plugins = [  # pylint: disable=invalid-name
    'tests.mock_vws.fixtures.prepared_requests',
    'tests.mock_vws.fixtures.credentials',
]

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


def _delete_all_targets(database_keys: VuforiaDatabase) -> None:
    """
    Delete all targets.

    Args:
        database_keys: The credentials to the Vuforia target database to delete
            all targets in.
    """
    response = list_targets(vuforia_database=database_keys)

    if 'results' not in response.json():  # pragma: no cover
        message = f'Results not found.\nResponse is: {response.json()}'
        LOGGER.debug(message)

    targets = response.json()['results']

    for target in targets:
        wait_for_target_processed(
            vuforia_database=database_keys,
            target_id=target,
        )

        # Even deleted targets can be matched by a query for a few seconds so
        # we change the target to inactive before deleting it.
        update_target(
            vuforia_database=database_keys,
            data={'active_flag': False},
            target_id=target,
        )
        wait_for_target_processed(
            vuforia_database=database_keys,
            target_id=target,
        )
        response = delete_target(
            vuforia_database=database_keys,
            target_id=target,
        )
        assert_vws_response(
            response=response,
            status_code=codes.OK,
            result_code=ResultCodes.SUCCESS,
        )


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

    try:
        response_json = response.json()
    except json.decoder.JSONDecodeError:  # pragma: no cover
        # This has been seen to happen in CI and this is here to help us debug
        # it.
        LOGGER.debug('Response text was:')
        LOGGER.debug(response.text)
        LOGGER.debug('Response status code was:')
        LOGGER.debug(response.status_code)
        raise

    new_target_id: str = response_json['target_id']
    return new_target_id


@pytest.fixture(params=[True, False], ids=['Real Vuforia', 'Mock Vuforia'])
def verify_mock_vuforia(
    request: SubRequest,
    vuforia_database: VuforiaDatabase,
    inactive_database: VuforiaDatabase,
) -> Generator:
    """
    Test functions which use this fixture are run twice. Once with the real
    Vuforia, and once with the mock.

    This is useful for verifying the mock.
    """
    skip_real = os.getenv('SKIP_REAL') == '1'
    skip_mock = os.getenv('SKIP_MOCK') == '1'

    use_real_vuforia = request.param

    if use_real_vuforia and skip_real:  # pragma: no cover
        pytest.skip()

    if not use_real_vuforia and skip_mock:  # pragma: no cover
        pytest.skip()

    working_database = VuforiaDatabase(
        database_name=vuforia_database.database_name,
        server_access_key=vuforia_database.server_access_key,
        server_secret_key=vuforia_database.server_secret_key,
        client_access_key=vuforia_database.client_access_key,
        client_secret_key=vuforia_database.client_secret_key,
    )

    inactive_database = VuforiaDatabase(
        state=States.PROJECT_INACTIVE,
        database_name=inactive_database.database_name,
        server_access_key=inactive_database.server_access_key,
        server_secret_key=inactive_database.server_secret_key,
        client_access_key=inactive_database.client_access_key,
        client_secret_key=inactive_database.client_secret_key,
    )
    if use_real_vuforia:
        _delete_all_targets(database_keys=vuforia_database)
        yield
    else:
        with MockVWS(processing_time_seconds=0.2) as mock:
            mock.add_database(database=working_database)
            mock.add_database(database=inactive_database)
            yield


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
    params=['a===', 'a'],
    ids=['Length >= 3', 'Length < 3'],
)
def not_base64_encoded(request: SubRequest) -> str:
    """
    Return a string which is not decodable as base64 data.
    """
    not_base64_encoded_string = request.param

    with pytest.raises(binascii.Error):
        base64.b64decode(not_base64_encoded_string)

    return not_base64_encoded_string
