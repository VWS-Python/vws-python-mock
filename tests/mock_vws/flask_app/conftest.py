"""Fixtures for flask app tests."""

from collections.abc import Iterator

import pytest
import responses
from beartype import beartype
from requests_mock_flask import add_flask_app_to_mock

from mock_vws._flask_server.target_manager import (
    TARGET_MANAGER,
    TARGET_MANAGER_FLASK_APP,
)
from mock_vws._flask_server.vwq import CLOUDRECO_FLASK_APP
from mock_vws._flask_server.vws import VWS_FLASK_APP
from tests.mock_vws.flask_app.helpers import EXAMPLE_URL_FOR_TARGET_MANAGER


@beartype
def _clear_target_manager() -> None:
    """Remove everything from the target manager which the Flask
    applications share.
    """
    for cloud_database in TARGET_MANAGER.cloud_databases:
        TARGET_MANAGER.remove_cloud_database(cloud_database=cloud_database)
    for vumark_database in TARGET_MANAGER.vumark_databases:
        TARGET_MANAGER.remove_vumark_database(vumark_database=vumark_database)
    for dataset_uuid in TARGET_MANAGER.model_target_datasets:
        TARGET_MANAGER.remove_model_target_dataset(dataset_uuid=dataset_uuid)


@pytest.fixture(autouse=True)
def _(*, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Enable a mock service backed by the Flask applications.

    The target manager is cleared before the test as well as after it,
    because the tests which use the in-process Flask backend fixture leave
    their databases in it, and which of those ran last in this process
    depends on how the tests are distributed.
    """
    _clear_target_manager()
    with responses.RequestsMock(
        assert_all_requests_are_fired=False,
    ) as mock_obj:
        add_flask_app_to_mock(
            mock_obj=mock_obj,
            flask_app=VWS_FLASK_APP,
            base_url="https://vws.vuforia.com",
        )

        add_flask_app_to_mock(
            mock_obj=mock_obj,
            flask_app=CLOUDRECO_FLASK_APP,
            base_url="https://cloudreco.vuforia.com",
        )

        add_flask_app_to_mock(
            mock_obj=mock_obj,
            flask_app=TARGET_MANAGER_FLASK_APP,
            base_url=EXAMPLE_URL_FOR_TARGET_MANAGER,
        )

        monkeypatch.setenv(
            name="TARGET_MANAGER_BASE_URL",
            value=EXAMPLE_URL_FOR_TARGET_MANAGER,
        )

        # Some tests serve an application themselves, on a local port, so
        # that they can make requests to it at the same time as each other.
        # Those requests are made for real rather than mocked.
        mock_obj.add_passthru(prefix="http://127.0.0.1")

        yield

    _clear_target_manager()
