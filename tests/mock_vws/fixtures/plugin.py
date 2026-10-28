"""Load shared API fixtures independently of backend adapters."""

pytest_plugins = [
    "tests.mock_vws.fixtures.prepared_requests",
    "tests.mock_vws.fixtures.model_target_prepared_requests",
    "tests.mock_vws.fixtures.api_contract",
]
