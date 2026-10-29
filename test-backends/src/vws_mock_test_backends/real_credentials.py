"""Load credentials for the explicit real-Vuforia backend."""

from pathlib import Path
from uuid import uuid4

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from vws_mock_contract_tests.fixtures.credentials import (
    InactiveVuMarkCloudDatabase,
    ModelTargetCredentials,
    VuMarkCloudDatabase,
)


class _InactiveVuMarkDatabaseSettings(BaseSettings):
    """Settings for an inactive VuMark database."""

    target_manager_database_name: str
    server_access_key: str
    server_secret_key: str

    model_config = SettingsConfigDict(
        env_prefix="INACTIVE_VUMARK_VUFORIA_",
        env_file=Path("vuforia_secrets.env"),
        extra="allow",
    )


class _VuMarkCloudDatabaseSettings(BaseSettings):
    """Settings for a VuMark Vuforia database."""

    target_manager_database_name: str
    server_access_key: str
    server_secret_key: str
    target_id: str
    processing_target_id: str = Field(default_factory=lambda: uuid4().hex)

    model_config = SettingsConfigDict(
        env_prefix="VUMARK_VUFORIA_",
        env_file=Path("vuforia_secrets.env"),
        extra="allow",
    )


class _ModelTargetSettings(BaseSettings):
    """Settings for the Model Target Web API."""

    client_id: str
    client_secret: str
    cad_data_url: str
    username: str
    password: str

    model_config = SettingsConfigDict(
        env_prefix="MODEL_TARGET_VUFORIA_",
        env_file=Path("vuforia_secrets.env"),
        extra="allow",
    )


def get_model_target_credentials() -> ModelTargetCredentials:
    """Return Model Target Web API credentials from environment
    variables.
    """
    settings = _ModelTargetSettings.model_validate(obj={})
    return ModelTargetCredentials(
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        cad_data_url=settings.cad_data_url,
        username=settings.username,
        password=settings.password,
    )


def get_real_inactive_vumark_database() -> InactiveVuMarkCloudDatabase:
    """Return inactive VuMark credentials from environment variables."""
    settings = _InactiveVuMarkDatabaseSettings.model_validate(obj={})
    return InactiveVuMarkCloudDatabase(
        target_manager_database_name=settings.target_manager_database_name,
        server_access_key=settings.server_access_key,
        server_secret_key=settings.server_secret_key,
    )


def get_real_vumark_database() -> VuMarkCloudDatabase:
    """Return VuMark VWS credentials from environment variables."""
    settings = _VuMarkCloudDatabaseSettings.model_validate(obj={})

    return VuMarkCloudDatabase(
        target_manager_database_name=settings.target_manager_database_name,
        server_access_key=settings.server_access_key,
        server_secret_key=settings.server_secret_key,
        target_id=settings.target_id,
        processing_target_id=settings.processing_target_id,
    )
