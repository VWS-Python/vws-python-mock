"""Tests for credential selection inside the backend adapter."""

from pathlib import Path

import pytest

from mock_vws.database import CloudDatabase
from mock_vws.states import States
from tests.mock_vws.fixtures.credentials import (
    InactiveVuMarkCloudDatabase,
    VuMarkCloudDatabase,
)
from tests.mock_vws.fixtures.real_credentials import (
    get_model_target_credentials,
)
from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend


@pytest.fixture(name="credentials_file", autouse=True, params=[False])
def fixture_credentials_file(
    *,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Isolate credential sources from real secrets and inherited settings."""
    valid = request.param
    assert isinstance(valid, bool)
    example = (
        Path(__file__).resolve().parents[3] / "vuforia_secrets.env.example"
    ).read_text()
    for line in example.splitlines():
        if "=" in line:
            variable = line.split(sep="=", maxsplit=1)[0]
            monkeypatch.delenv(name=variable, raising=False)
    monkeypatch.chdir(path=tmp_path)
    contents = example if valid else "UNRELATED_SETTING=invalid\n"
    _ = (tmp_path / "vuforia_secrets.env").write_text(data=contents)


@pytest.fixture(
    name="_vws_backend",
    params=[VuforiaBackend.MOCK, VuforiaBackend.FLASK_IN_PROCESS],
    ids=["in-memory", "flask"],
)
def fixture_backend_selection(
    *, request: pytest.FixtureRequest
) -> VuforiaBackend:
    """Select credentials without setting up a service or making
    requests.
    """
    backend = request.param
    assert isinstance(backend, VuforiaBackend)
    return backend


@pytest.mark.usefixtures("_vws_backend")
def test_mock_credentials_ignore_settings(
    *,
    vuforia_database: CloudDatabase,
    inactive_cloud_database: CloudDatabase,
    vumark_vuforia_database: VuMarkCloudDatabase,
    inactive_vumark_database: InactiveVuMarkCloudDatabase,
) -> None:
    """Both mock adapters supply usable credentials with invalid
    settings.
    """
    assert vuforia_database.state == States.WORKING
    assert inactive_cloud_database.state == States.PROJECT_INACTIVE
    assert (
        vuforia_database.server_access_key
        != inactive_cloud_database.server_access_key
    )
    assert (
        vumark_vuforia_database.target_id
        != vumark_vuforia_database.processing_target_id
    )
    assert (
        inactive_vumark_database.server_access_key
        != vumark_vuforia_database.server_access_key
    )


def test_standalone_mock_credentials(
    *, vuforia_database: CloudDatabase
) -> None:
    """Implementation tests with no selected backend also need no settings."""
    assert vuforia_database.state == States.WORKING
    assert vuforia_database.server_access_key != ""


@pytest.mark.parametrize(
    argnames="credentials_file", argvalues=[True], indirect=True
)
@pytest.mark.usefixtures("_vws_backend")
@pytest.mark.parametrize(
    argnames="_vws_backend", argvalues=[VuforiaBackend.REAL], indirect=True
)
def test_real_credentials_use_settings(
    *,
    vuforia_database: CloudDatabase,
    inactive_cloud_database: CloudDatabase,
    vumark_vuforia_database: VuMarkCloudDatabase,
    inactive_vumark_database: InactiveVuMarkCloudDatabase,
) -> None:
    """Only the real selection loads each account from its settings
    file.
    """
    assert vuforia_database.database_id == "example_database_id"
    assert vuforia_database.server_access_key == "example_server_access_key"
    assert inactive_cloud_database.state == States.PROJECT_INACTIVE
    assert (
        inactive_cloud_database.client_access_key
        == "example_inactive_client_access_key"
    )
    assert vumark_vuforia_database.target_id == "examplevumarktargetid"
    assert (
        inactive_vumark_database.server_access_key
        == "example_inactive_vumark_server_access_key"
    )


@pytest.mark.parametrize(
    argnames="credentials_file", argvalues=[True], indirect=True
)
def test_real_model_target_settings() -> None:
    """The real Model Target loader keeps its settings and input data."""
    credentials = get_model_target_credentials()
    assert credentials.client_id == "example_model_target_client_id"
    assert credentials.client_secret == "example_model_target_client_secret"
    assert credentials.cad_data_url == "https://example.com/model.glb"
    assert credentials.username == "user@example.com"
    assert credentials.password == "example_model_target_password"
