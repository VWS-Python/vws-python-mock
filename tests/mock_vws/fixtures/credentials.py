"""
Fixtures for credentials for Vuforia databases.
"""

import os

import pytest

from mock_vws.database import VuforiaDatabase
from mock_vws.states import States


@pytest.fixture()
def vuforia_database() -> VuforiaDatabase:
    """
    Return VWS credentials from environment variables.
    """
    credentials: VuforiaDatabase = VuforiaDatabase(
        database_name=os.environ['VUFORIA_TARGET_MANAGER_DATABASE_NAME'],
        server_access_key=os.environ['VUFORIA_SERVER_ACCESS_KEY'],
        server_secret_key=os.environ['VUFORIA_SERVER_SECRET_KEY'],
        client_access_key=os.environ['VUFORIA_CLIENT_ACCESS_KEY'],
        client_secret_key=os.environ['VUFORIA_CLIENT_SECRET_KEY'],
        state=States.WORKING,
    )
    return credentials


@pytest.fixture()
def inactive_database() -> VuforiaDatabase:
    """
    Return VWS credentials for an inactive project from environment variables.
    """
    credentials: VuforiaDatabase = VuforiaDatabase(
        database_name=os.environ[
            'INACTIVE_VUFORIA_TARGET_MANAGER_DATABASE_NAME'
        ],
        server_access_key=os.environ['INACTIVE_VUFORIA_SERVER_ACCESS_KEY'],
        server_secret_key=os.environ['INACTIVE_VUFORIA_SERVER_SECRET_KEY'],
        client_access_key=os.environ['INACTIVE_VUFORIA_CLIENT_ACCESS_KEY'],
        client_secret_key=os.environ['INACTIVE_VUFORIA_CLIENT_SECRET_KEY'],
        state=States.PROJECT_INACTIVE,
    )
    return credentials
