"""Compatibility imports for the separately installed server package."""

from flask import Flask

from vws_mock_server.vws import (
    VWS_FLASK_APP as _FLASK_APP,
)
from vws_mock_server.vws import (
    VWSSettings,
)

VWS_FLASK_APP: Flask = _FLASK_APP

__all__ = ["VWS_FLASK_APP", "VWSSettings"]


# Containers execute this process entry point; import-driven tests use its API.
if __name__ == "__main__":  # pragma: no cover
    SETTINGS = VWSSettings.model_validate(obj={})
    VWS_FLASK_APP.run(host=SETTINGS.vws_host)
