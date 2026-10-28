"""Compatibility imports for the separately installed server package."""

from flask import Flask

from vws_mock_server.vwq import (
    CLOUDRECO_FLASK_APP as _FLASK_APP,
)
from vws_mock_server.vwq import (
    VWQSettings,
)

CLOUDRECO_FLASK_APP: Flask = _FLASK_APP

__all__ = ["CLOUDRECO_FLASK_APP", "VWQSettings"]


# Containers execute this process entry point; import-driven tests use its API.
if __name__ == "__main__":  # pragma: no cover
    SETTINGS = VWQSettings.model_validate(obj={})
    CLOUDRECO_FLASK_APP.run(host=SETTINGS.vwq_host)
