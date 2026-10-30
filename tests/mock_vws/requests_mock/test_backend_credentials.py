"""Tests for credential selection inside the backend adapter."""

from pathlib import Path

import pytest

from tests.mock_vws.fixtures.real_credentials import (
    get_model_target_credentials,
)
from vws_mock_contract_tests.fixtures.credentials import (
    InactiveVuMarkCloudDatabase,
    VuMarkCloudDatabase,
)


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


def test_credentials_without_backend(
    vumark_vuforia_database: VuMarkCloudDatabase,
    inactive_vumark_database: InactiveVuMarkCloudDatabase,
) -> None:
    """Implementation tests receive credentials without real settings or a
    backend selector.
    """
    assert vumark_vuforia_database.server_access_key != ""
    assert vumark_vuforia_database.server_secret_key != ""
    assert inactive_vumark_database.server_access_key != ""
    assert inactive_vumark_database.server_secret_key != ""
    assert (
        vumark_vuforia_database.server_access_key
        != inactive_vumark_database.server_access_key
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
