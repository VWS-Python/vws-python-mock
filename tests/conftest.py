"""Register shared fixtures and the backend adapters for this
repository.
"""

pytest_plugins = [
    "tests.mock_vws.fixtures.plugin",
    "tests.mock_vws.fixtures.vuforia_backends",
]
