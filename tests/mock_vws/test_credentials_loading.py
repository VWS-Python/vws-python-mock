"""Tests for loading credentials for the test suite."""

from pathlib import Path

import pytest
from beartype import beartype
from pydantic import ValidationError
from pydantic_settings import BaseSettings

from tests.mock_vws.fixtures import credentials


class _UnsatisfiableSettings(BaseSettings):
    """Settings with a field which nothing provides."""

    unsatisfiable_field: str


@beartype
def test_missing_secrets_file(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A missing secrets file gives an error which names the file."""
    secrets_file = tmp_path / "vuforia_secrets.env"
    monkeypatch.setattr(
        target=credentials,
        name="_SECRETS_FILE",
        value=secrets_file,
    )
    monkeypatch.setattr(
        target=credentials,
        name="_REPOSITORY_ROOT",
        value=tmp_path,
    )

    with pytest.raises(expected_exception=FileNotFoundError) as exc:
        credentials.load_settings(settings_class=_UnsatisfiableSettings)

    expected_message = (
        f"{secrets_file} not found. "
        "Copy vuforia_secrets.env.example to vuforia_secrets.env in "
        f"{tmp_path} and fill it in. "
        "See the contributing documentation."
    )
    assert str(object=exc.value) == expected_message


@beartype
def test_secrets_file_present(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Validation errors are not hidden when the secrets file exists."""
    secrets_file = tmp_path / "vuforia_secrets.env"
    secrets_file.touch()
    monkeypatch.setattr(
        target=credentials,
        name="_SECRETS_FILE",
        value=secrets_file,
    )

    with pytest.raises(expected_exception=ValidationError):
        credentials.load_settings(settings_class=_UnsatisfiableSettings)
