"""Register shared fixtures and the backend adapters for this
repository.
"""

pytest_plugins = [
    "tests.mock_vws.fixtures.prepared_requests",
    "tests.mock_vws.fixtures.vuforia_backends",
    "tests.mock_vws.fixtures.model_target_prepared_requests",
    "tests.mock_vws.fixtures.api_contract",
]
