"""
Fixtures for credentials for Vuforia databases.
"""

import os

import pytest

from tests.mock_vws.utils import VuforiaDatabase


@pytest.fixture()
def vuforia_database_keys() -> VuforiaDatabase:
    """
    Return VWS credentials from environment variables.
    """
    credentials: VuforiaDatabase = VuforiaDatabase(
        database_name=os.environ['VUFORIA_TARGET_MANAGER_DATABASE_NAME'],
        server_access_key=os.environ['VUFORIA_SERVER_ACCESS_KEY'],
        server_secret_key=os.environ['VUFORIA_SERVER_SECRET_KEY'],
        client_access_key=os.environ['VUFORIA_CLIENT_ACCESS_KEY'],
        client_secret_key=os.environ['VUFORIA_CLIENT_SECRET_KEY'],
    )
    return credentials


@pytest.fixture()
def inactive_database_keys() -> VuforiaDatabase:
    """
    Return VWS credentials for an inactive project from environment variables.
    """
    credentials: VuforiaDatabase = VuforiaDatabase(
        database_name=os.
        environ['INACTIVE_VUFORIA_TARGET_MANAGER_DATABASE_NAME'],
        server_access_key=os.environ['INACTIVE_VUFORIA_SERVER_ACCESS_KEY'],
        server_secret_key=os.environ['INACTIVE_VUFORIA_SERVER_SECRET_KEY'],
        client_access_key=os.environ['INACTIVE_VUFORIA_CLIENT_ACCESS_KEY'],
        client_secret_key=os.environ['INACTIVE_VUFORIA_CLIENT_SECRET_KEY'],
    )
    return credentials
