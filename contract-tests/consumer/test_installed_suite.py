"""Exercise built wheels from a separate consumer environment."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _run(*, args: list[str | Path], cwd: Path) -> None:
    """Run a local tool, failing the test if it fails."""
    # Commands use a local executable and fixed options or built wheel paths.
    _ = subprocess.run(args=args, cwd=cwd, check=True)  # noqa: S603


def test_installed_suite(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Collect without an implementation, then run the Flask adapter."""
    consumer = Path(__file__).resolve().parent
    repository = consumer.parent.parent
    dist = tmp_path / "dist"
    environment = tmp_path / "venv"
    uv = shutil.which(cmd="uv")
    assert uv is not None
    monkeypatch.delenv(name="PYTHONPATH", raising=False)

    _run(
        args=[uv, "build", "--all-packages", "--wheel", "--out-dir", dist],
        cwd=repository,
    )
    _run(
        args=[uv, "venv", "--python", sys.executable, environment],
        cwd=tmp_path,
    )
    python = environment / (
        "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    )
    suite = next(dist.glob(pattern="vws_mock_contract_tests-*.whl"))
    _run(args=[uv, "pip", "install", "--python", python, suite], cwd=tmp_path)
    for filename in (
        "pytest.ini",
        "dependency_checks.py",
        "core_checks.py",
        "contract_checks.py",
    ):
        _ = shutil.copyfile(src=consumer / filename, dst=tmp_path / filename)

    _run(
        args=[
            python,
            "-m",
            "pytest",
            "-p",
            "dependency_checks",
            "-p",
            "vws_mock_contract_tests.fixtures.plugin",
            "--pyargs",
            "vws_mock_contract_tests",
            "--collect-only",
            "-q",
        ],
        cwd=tmp_path,
    )
    core = next(dist.glob(pattern="vws_python_mock-*.whl"))
    _run(args=[uv, "pip", "install", "--python", python, core], cwd=tmp_path)
    _run(
        args=[
            python,
            "-m",
            "pytest",
            "-p",
            "core_checks",
            "--pyargs",
            "vws_mock_contract_tests.vumark_generation_api",
            "--collect-only",
            "-q",
        ],
        cwd=tmp_path,
    )
    _run(
        args=[
            uv,
            "pip",
            "install",
            "--python",
            python,
            *dist.glob(pattern="*.whl"),
        ],
        cwd=tmp_path,
    )
    health_tests = tmp_path / "test_server_health.py"
    _ = shutil.copyfile(
        src=repository
        / "server/tests/vws_mock_server_tests/test_healthcheck.py",
        dst=health_tests,
    )
    _run(args=[python, "-m", "pytest", health_tests, "-q"], cwd=tmp_path)
    _run(
        args=[
            python,
            "-m",
            "pytest",
            "-p",
            "contract_checks",
            "-p",
            "vws_mock_contract_tests.fixtures.plugin",
            "-p",
            "vws_mock_test_backends.vuforia_backends",
            "--pyargs",
            os.environ.get(
                key="CONTRACT_TEST_TARGET",
                default="vws_mock_contract_tests.vumark_generation_api",
            ),
            "--skip-backend=real",
            "--skip-backend=mock",
            "-q",
        ],
        cwd=tmp_path,
    )
