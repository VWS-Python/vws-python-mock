"""Compatibility import for the server package's health check."""

import sys

from vws_mock_server.healthcheck import flask_app_healthy

__all__ = ["flask_app_healthy"]


# Containers execute this process entry point; import-driven tests use its API.
if __name__ == "__main__":  # pragma: no cover
    sys.exit(int(not flask_app_healthy(port=5000)))
