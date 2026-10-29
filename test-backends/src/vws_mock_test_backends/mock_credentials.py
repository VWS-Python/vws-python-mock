"""Synthetic credentials for mock backend adapters."""

from uuid import uuid4

from beartype import beartype

from mock_vws.database import CloudDatabase
from mock_vws.states import States
from vws_mock_contract_tests.fixtures.credentials import (
    InactiveVuMarkCloudDatabase,
    ModelTargetCredentials,
    VuMarkCloudDatabase,
)


@beartype
def get_mock_cloud_database() -> CloudDatabase:
    """Create synthetic credentials for the mock backend."""
    return CloudDatabase()


@beartype
def get_mock_inactive_cloud_database() -> CloudDatabase:
    """Create synthetic credentials for the mock backend."""
    return CloudDatabase(state=States.PROJECT_INACTIVE)


@beartype
def get_mock_inactive_vumark_database() -> InactiveVuMarkCloudDatabase:
    """Create synthetic credentials for the mock backend."""
    return InactiveVuMarkCloudDatabase(
        target_manager_database_name=uuid4().hex,
        server_access_key=uuid4().hex,
        server_secret_key=uuid4().hex,
    )


@beartype
def get_mock_vumark_database() -> VuMarkCloudDatabase:
    """Create synthetic credentials for the mock backend."""
    return VuMarkCloudDatabase(
        target_manager_database_name=uuid4().hex,
        server_access_key=uuid4().hex,
        server_secret_key=uuid4().hex,
        target_id=uuid4().hex,
        processing_target_id=uuid4().hex,
    )


@beartype
def get_mock_model_target_credentials() -> ModelTargetCredentials:
    """Create synthetic credentials for the mock backend."""
    return ModelTargetCredentials(
        client_id="client-id",
        client_secret="client-secret",
        cad_data_url="https://example.com/model.glb",
        username="user@example.com",
        password="password",
    )
