"""Fixtures for credentials for Vuforia databases."""

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict

from mock_vws.database import CloudDatabase
from mock_vws.states import States


class _CloudDatabaseSettings(BaseSettings):
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


class _InactiveCloudDatabaseSettings(_CloudDatabaseSettings):
    """Settings for an inactive Vuforia database."""

    model_config = SettingsConfigDict(
        env_prefix="INACTIVE_VUFORIA_",
        env_file=Path("vuforia_secrets.env"),
        extra="allow",
    )


class _VuMarkCloudDatabaseSettings(BaseSettings):
    """Settings for a VuMark Vuforia database."""

    target_manager_database_name: str
    server_access_key: str
    server_secret_key: str
    target_id: str

    model_config = SettingsConfigDict(
        env_prefix="VUMARK_VUFORIA_",
        env_file=Path("vuforia_secrets.env"),
        extra="allow",
    )


@dataclass(frozen=True)
class VuMarkCloudDatabase:
    """Credentials for the VuMark generation API."""

    target_manager_database_name: str = field(repr=False)
    server_access_key: str = field(repr=False)
    server_secret_key: str = field(repr=False)
    target_id: str = field(repr=False)


@pytest.fixture
def vuforia_database() -> CloudDatabase:
    """Return VWS credentials from environment variables."""
    settings = _CloudDatabaseSettings.model_validate(obj={})
    return CloudDatabase(
        database_name=settings.target_manager_database_name,
        server_access_key=settings.server_access_key,
        server_secret_key=settings.server_secret_key,
        client_access_key=settings.client_access_key,
        client_secret_key=settings.client_secret_key,
        state=States.WORKING,
    )


@pytest.fixture
def inactive_database() -> CloudDatabase:
    """
    Return VWS credentials for an inactive project from environment
    variables.
    """
    settings = _InactiveCloudDatabaseSettings.model_validate(obj={})
    return CloudDatabase(
        database_name=settings.target_manager_database_name,
        server_access_key=settings.server_access_key,
        server_secret_key=settings.server_secret_key,
        client_access_key=settings.client_access_key,
        client_secret_key=settings.client_secret_key,
        state=States.PROJECT_INACTIVE,
    )


@pytest.fixture
def vumark_vuforia_database() -> VuMarkCloudDatabase:
    """Return VuMark VWS credentials from environment variables."""
    settings = _VuMarkCloudDatabaseSettings.model_validate(obj={})

    return VuMarkCloudDatabase(
        target_manager_database_name=settings.target_manager_database_name,
        server_access_key=settings.server_access_key,
        server_secret_key=settings.server_secret_key,
        target_id=settings.target_id,
    )
