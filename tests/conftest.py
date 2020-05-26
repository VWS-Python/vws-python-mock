"""
Configuration, plugins and fixtures for `pytest`.
"""

import base64
import binascii
import io
import logging
import uuid
from typing import Any, List, Tuple

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

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


def is_internal_server_error(
    err: Tuple,
    *args: Tuple,
) -> bool:  # pragma: no cover
    """
    Return whether the error is an ``UnexpectedEmptyInternalServerError``, so
    that we can retry a test if it is.
    """
    assert args
    message = f'Error hit: {err[0]}'
    LOGGER.debug(message)
    is_specific_error = bool(err[0] == UnexpectedEmptyInternalServerError)
    message = f'Is UnexpectedEmptyInternalServerError: {is_specific_error}'
    LOGGER.debug(message)
    return is_specific_error


_retry_marker = pytest.mark.flaky(
    max_runs=3,
    rerun_filter=is_internal_server_error,
)

def pytest_collection_modifyitems(items: List[pytest.Function]) -> None:
    """
    Add a marker to each test which will retry the test if an
    ``UnexpectedEmptyInternalServerError`` is raised.
    """
    for item in items:
        item.add_marker(_retry_marker)


@pytest.fixture()
def target_id_factory(
    image_file_success_state_low_rating: io.BytesIO,
    vuforia_database: VuforiaDatabase,
) -> Any:
    """
    Return a callable which the target ID of a target in the database.
    The callable uses ``add_target_to_vws`` which is flaky.
    We use ``flaky`` from PyPI to re-run tests which raise
    ``UnexpectedEmptyInternalServerError`` as that helper does.
    That does not allow us to retry when an error happens in test setup:
    https://github.com/box/flaky/issues/135.

    We could use ``pytest-rerunfailures`` instead but that does not allow us to
    specify which exceptions to retry on:
    https://github.com/pytest-dev/pytest-rerunfailures/issues/58.
    https://github.com/pytest-dev/pytest-rerunfailures/issues/101.

    The target is one which will have a 'success' status when processed.
    """

    class Factory:

        def get(self) -> str:
            image_data = image_file_success_state_low_rating.read()
            image_data_encoded = base64.b64encode(image_data).decode('ascii')
            name = uuid.uuid4().hex

            data = {
                'name': name,
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

    return Factory()


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
