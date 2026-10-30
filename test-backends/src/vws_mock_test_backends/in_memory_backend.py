"""In-memory mock setup and state for the contract-test adapter."""

from collections.abc import Generator

import pytest
from beartype import beartype

from mock_vws import MockVWS
from mock_vws.database import VuMarkDatabase
from mock_vws.states import States
from vws_mock_contract_tests.fixtures.credentials import (
    InactiveVuMarkCloudDatabase,
    VuMarkCloudDatabase,
)
from vws_mock_test_backends.mock_databases import create_vumark_database


@beartype
def enable_in_memory_vuforia(
    *,
    vumark_vuforia_database: VuMarkCloudDatabase,
    inactive_vumark_database: InactiveVuMarkCloudDatabase,
    monkeypatch: pytest.MonkeyPatch,
    base_vws_url: str,
) -> Generator[None]:
    """Test against the in-memory mock Vuforia."""
    assert bool(monkeypatch)
    vumark_database = create_vumark_database(
        vumark_vuforia_database=vumark_vuforia_database,
    )
    inactive_vumark_db = VuMarkDatabase(
        state=States.PROJECT_INACTIVE,
        database_name=inactive_vumark_database.target_manager_database_name,
        server_access_key=inactive_vumark_database.server_access_key,
        server_secret_key=inactive_vumark_database.server_secret_key,
    )

    with MockVWS(base_vws_url=base_vws_url) as mock:
        mock.add_vumark_database(vumark_database=vumark_database)
        mock.add_vumark_database(vumark_database=inactive_vumark_db)
        yield


@beartype
def enable_in_memory_model_targets(
    *,
    monkeypatch: pytest.MonkeyPatch,
    base_vws_url: str,
) -> Generator[None]:
    """Test against the in-memory mock Model Target Web API."""
    assert bool(monkeypatch)
    with MockVWS(base_vws_url=base_vws_url):
        yield
