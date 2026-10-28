#!/usr/bin/env bash
set -euo pipefail

CHECK_DIR="$(mktemp -d)"
trap 'rm -rf "${CHECK_DIR}"' EXIT

uv build --all-packages --wheel --out-dir "${CHECK_DIR}/dist"
uv venv --python 3.15 "${CHECK_DIR}/consumer"
CONSUMER_PYTHON="${CHECK_DIR}/consumer/bin/python"
uv pip install --python "${CONSUMER_PYTHON}" "${CHECK_DIR}"/dist/vws_mock_contract_tests-*.whl

cd "${CHECK_DIR}"
unset PYTHONPATH
printf '[pytest]\n' > pytest.ini

"${CONSUMER_PYTHON}" - << 'PY'
import importlib.util

assert importlib.util.find_spec(name="mock_vws") is None
assert importlib.util.find_spec(name="flask") is None
PY

"${CONSUMER_PYTHON}" -m pytest \
    -c pytest.ini \
    -p vws_mock_contract_tests.fixtures.plugin \
    --pyargs vws_mock_contract_tests --collect-only -q

uv pip install --python "${CONSUMER_PYTHON}" \
    "${CHECK_DIR}"/dist/vws_python_mock-*.whl \
    "${CHECK_DIR}"/dist/vws_mock_test_backends-*.whl

cat > consumer_contract.py << 'PY'
"""Check the lifecycle boundary of the explicitly selected adapter."""

import sys

import pytest


@pytest.fixture(autouse=True)
def ready(request: pytest.FixtureRequest) -> None:
    """Check that the adapter's public setup fixture yields None."""
    for name in ("verify_mock_vuforia", "mock_only_vuforia"):
        if name in request.fixturenames:
            assert request.getfixturevalue(argname=name) is None


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Keep the core repository's tests outside the consumer process."""
    del session, exitstatus
    assert not any(name.startswith("tests.mock_vws") for name in sys.modules)
PY

"${CONSUMER_PYTHON}" -m pytest \
    -c pytest.ini \
    -p consumer_contract \
    -p vws_mock_contract_tests.fixtures.plugin \
    -p vws_mock_test_backends.vuforia_backends \
    --pyargs "${CONTRACT_TEST_TARGET:-vws_mock_contract_tests.database_summary}" \
    --skip-backend=real --skip-backend=mock -q
