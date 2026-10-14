"""Register shared fixtures and the backend adapters for this
repository.
"""

# `credentials` must be listed before modules that import from it.
# If listed later, those imports happen before pytest can register it for
# assertion rewriting, causing a PytestAssertRewriteWarning.
pytest_plugins = [
    "tests.mock_vws.fixtures.credentials",
    "tests.mock_vws.fixtures.prepared_requests",
    "tests.mock_vws.fixtures.vuforia_backends",
    "tests.mock_vws.fixtures.model_target_prepared_requests",
    "tests.mock_vws.fixtures.api_contract",
]
