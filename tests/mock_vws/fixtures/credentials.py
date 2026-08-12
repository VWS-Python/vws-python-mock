"""Fixtures for credentials for Vuforia databases."""

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from mock_vws.database import CloudDatabase
from mock_vws.states import States

_REPOSITORY_ROOT = Path(__file__).parents[3]
_SECRETS_FILE = _REPOSITORY_ROOT / "vuforia_secrets.env"


def load_settings[SettingsT: BaseSettings](
    *,
    settings_class: type[SettingsT],
) -> SettingsT:
    """Load settings, pointing at the secrets file if it is missing.

    Without this, a missing secrets file gives a bare list of "Field
    required" errors which never names the file to create.
    """
    try:
        return settings_class.model_validate(obj={})
    except ValidationError:
        if _SECRETS_FILE.exists():
            raise
        message = (
            f"{_SECRETS_FILE} not found. "
            "Copy vuforia_secrets.env.example to vuforia_secrets.env in "
            f"{_REPOSITORY_ROOT} and fill it in. "
            "See the contributing documentation."
        )
        raise FileNotFoundError(message) from None


class _CloudDatabaseSettings(BaseSettings):
    """Settings for a Vuforia database."""

    target_manager_database_name: str
    server_access_key: str
    server_secret_key: str
    client_access_key: str
    client_secret_key: str

    model_config = SettingsConfigDict(
        env_prefix="VUFORIA_",
        env_file=_SECRETS_FILE,
        extra="allow",
    )


class _WorkingCloudDatabaseSettings(_CloudDatabaseSettings):
    """Settings for the working Vuforia database.

    Only the working database has an ID, because only endpoints which name
    a database in their path need one.
    """

    database_id: str


class _InactiveCloudDatabaseSettings(_CloudDatabaseSettings):
    """Settings for an inactive Vuforia database."""

    model_config = SettingsConfigDict(
        env_prefix="INACTIVE_VUFORIA_",
        env_file=_SECRETS_FILE,
        extra="allow",
    )


class _InactiveVuMarkDatabaseSettings(BaseSettings):
    """Settings for an inactive VuMark database."""

    target_manager_database_name: str
    server_access_key: str
    server_secret_key: str

    model_config = SettingsConfigDict(
        env_prefix="INACTIVE_VUMARK_VUFORIA_",
        env_file=_SECRETS_FILE,
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
        env_file=_SECRETS_FILE,
        extra="allow",
    )


class _ModelTargetSettings(BaseSettings):
    """Settings for the Model Target Web API."""

    client_id: str
    client_secret: str
    cad_data_url: str

    model_config = SettingsConfigDict(
        env_prefix="MODEL_TARGET_VUFORIA_",
        env_file=_SECRETS_FILE,
        extra="allow",
    )


@dataclass(frozen=True, kw_only=True)
class InactiveVuMarkCloudDatabase:
    """Credentials for an inactive VuMark database."""

    target_manager_database_name: str = field(repr=False)
    server_access_key: str = field(repr=False)
    server_secret_key: str = field(repr=False)


@dataclass(frozen=True, kw_only=True)
class VuMarkCloudDatabase:
    """Credentials for the VuMark generation API."""

    target_manager_database_name: str = field(repr=False)
    server_access_key: str = field(repr=False)
    server_secret_key: str = field(repr=False)
    target_id: str = field(repr=False)
    processing_target_id: str = field(repr=False)


@dataclass(frozen=True, kw_only=True)
class ModelTargetCredentials:
    """Credentials and input data for the Model Target Web API."""

    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    cad_data_url: str = field(repr=False)


def get_model_target_credentials() -> ModelTargetCredentials:
    """Return Model Target Web API credentials from environment
    variables.
    """
    settings = load_settings(settings_class=_ModelTargetSettings)
    return ModelTargetCredentials(
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        cad_data_url=settings.cad_data_url,
    )


@pytest.fixture
def vuforia_database() -> CloudDatabase:
    """Return VWS credentials from environment variables."""
    settings = load_settings(settings_class=_WorkingCloudDatabaseSettings)
    return CloudDatabase(
        database_id=settings.database_id,
        database_name=settings.target_manager_database_name,
        server_access_key=settings.server_access_key,
        server_secret_key=settings.server_secret_key,
        client_access_key=settings.client_access_key,
        client_secret_key=settings.client_secret_key,
        state=States.WORKING,
    )


@pytest.fixture
def inactive_cloud_database() -> CloudDatabase:
    """
    Return VWS credentials for an inactive project from environment
    variables.
    """
    settings = load_settings(settings_class=_InactiveCloudDatabaseSettings)
    return CloudDatabase(
        database_name=settings.target_manager_database_name,
        server_access_key=settings.server_access_key,
        server_secret_key=settings.server_secret_key,
        client_access_key=settings.client_access_key,
        client_secret_key=settings.client_secret_key,
        state=States.PROJECT_INACTIVE,
    )


@pytest.fixture
def inactive_vumark_database() -> InactiveVuMarkCloudDatabase:
    """Return inactive VuMark credentials from environment variables."""
    settings = load_settings(settings_class=_InactiveVuMarkDatabaseSettings)
    return InactiveVuMarkCloudDatabase(
        target_manager_database_name=settings.target_manager_database_name,
        server_access_key=settings.server_access_key,
        server_secret_key=settings.server_secret_key,
    )


@pytest.fixture
def vumark_vuforia_database() -> VuMarkCloudDatabase:
    """Return VuMark VWS credentials from environment variables."""
    settings = load_settings(settings_class=_VuMarkCloudDatabaseSettings)

    return VuMarkCloudDatabase(
        target_manager_database_name=settings.target_manager_database_name,
        server_access_key=settings.server_access_key,
        server_secret_key=settings.server_secret_key,
        target_id=settings.target_id,
        processing_target_id=settings.processing_target_id,
    )
