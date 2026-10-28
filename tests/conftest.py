"""Register shared fixtures and the backend adapters for this
repository.
"""

pytest_plugins = [
    "vws_mock_contract_tests.fixtures.plugin",
    "vws_mock_test_backends.vuforia_backends",
]
