"""Compatibility imports for the separately installed server package."""

from flask import Flask

from vws_mock_server.target_manager import (
    TARGET_MANAGER,
    TargetManagerSettings,
    remove_oauth2_client_credential,
)
from vws_mock_server.target_manager import (
    TARGET_MANAGER_FLASK_APP as _FLASK_APP,
)

TARGET_MANAGER_FLASK_APP: Flask = _FLASK_APP

__all__ = [
    "TARGET_MANAGER",
    "TARGET_MANAGER_FLASK_APP",
    "TargetManagerSettings",
    "remove_oauth2_client_credential",
]


# Containers execute this process entry point; import-driven tests use its API.
if __name__ == "__main__":  # pragma: no cover
    SETTINGS = TargetManagerSettings.model_validate(obj={})
    TARGET_MANAGER_FLASK_APP.run(host=SETTINGS.target_manager_host)
