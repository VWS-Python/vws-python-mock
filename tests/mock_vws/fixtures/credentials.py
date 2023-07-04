"""
Fixtures for credentials for Vuforia databases.
"""

from pathlib import Path

import pytest
from mock_vws.database import VuforiaDatabase
from mock_vws.states import States
from pydantic_settings import BaseSettings, SettingsConfigDict


class _VuforiaDatabaseSettings(BaseSettings):
    """Settings for a Vuforia database."""

    target_manager_database_name: str
    server_access_key: str
    server_secret_key: str
    client_access_key: str
    client_secret_key: str

    model_config = SettingsConfigDict(
        env_prefix="VUFORIA_",
        env_file=Path("vuforia_secrets.env"),
        extra="allow",
    )


class _InactiveVuforiaDatabaseSettings(_VuforiaDatabaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INACTIVE_VUFORIA_",
        env_file=Path("vuforia_secrets.env"),
        extra="allow",
    )


@pytest.fixture()
def vuforia_database() -> VuforiaDatabase:
    """
    Return VWS credentials from environment variables.
    """
    settings = _VuforiaDatabaseSettings.model_validate(obj={})
    return VuforiaDatabase(
        database_name=settings.target_manager_database_name,
        server_access_key=settings.server_access_key,
        server_secret_key=settings.server_secret_key,
        client_access_key=settings.client_access_key,
        client_secret_key=settings.client_secret_key,
        state=States.WORKING,
    )


@pytest.fixture()
def inactive_database() -> VuforiaDatabase:
    """
    Return VWS credentials for an inactive project from environment variables.
    """
    settings = _InactiveVuforiaDatabaseSettings.model_validate(obj={})
    return VuforiaDatabase(
        database_name=settings.target_manager_database_name,
        server_access_key=settings.server_access_key,
        server_secret_key=settings.server_secret_key,
        client_access_key=settings.client_access_key,
        client_secret_key=settings.client_secret_key,
        state=States.PROJECT_INACTIVE,
    )
