"""Compatibility entry point for explicit pytest plugins."""

from vws_mock_test_backends.vuforia_backends import VuforiaBackend

__all__ = ["VuforiaBackend"]

pytest_plugins = ["vws_mock_test_backends.vuforia_backends"]
