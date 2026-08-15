"""Tests for concurrent requests to the mock Flask applications.

The Docker containers serve requests on threads, so requests which change
state can run at the same time as requests which read it.
"""

import base64
import io
import sys
import threading
import uuid
from collections.abc import Callable, Iterator
from http import HTTPMethod, HTTPStatus

import pytest
import requests
from PIL import Image
from werkzeug.serving import BaseWSGIServer, make_server

from mock_vws._flask_server.target_manager import (
    TARGET_MANAGER,
    TARGET_MANAGER_FLASK_APP,
)
from mock_vws.database import CloudDatabase

_NUM_WRITER_THREADS = 4
_NUM_READER_THREADS = 4
_NUM_REQUESTS_PER_WRITER = 25
# Requests which read the databases iterate the targets of each database, so
# the more targets there are, the longer a request which changes a database
# has to interleave with a request which reads it.
_NUM_EXISTING_TARGETS = 50


@pytest.fixture(name="small_image_base64")
def fixture_small_image_base64() -> str:
    """A base64 encoded image which is quick to process."""
    image_buffer = io.BytesIO()
    image = Image.new(mode="RGB", size=(64, 64), color=(0, 255, 0))
    image.save(fp=image_buffer, format="PNG")
    return base64.b64encode(s=image_buffer.getvalue()).decode(encoding="utf-8")


@pytest.fixture(name="target_manager_base_url")
def fixture_target_manager_base_url(
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[str]:
    """Serve the target manager application on multiple threads.

    This uses a real server rather than ``responses`` because ``responses``
    handles one request at a time, within the calling thread.
    """
    # The default target rater inspects each image every time that a target is
    # serialized, which makes the many requests in these tests slow.
    monkeypatch.setenv(name="TARGET_RATER", value="perfect")
    # Threads are switched much more often than they are by default, so that
    # requests interleave with each other often enough for these tests to fail
    # in a single run when state is not guarded by a lock.
    original_switch_interval = sys.getswitchinterval()
    sys.setswitchinterval(0.000_001)
    server: BaseWSGIServer = make_server(
        host="127.0.0.1",
        port=0,
        app=TARGET_MANAGER_FLASK_APP,
        threaded=True,
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server_thread.join()
        server.server_close()
        sys.setswitchinterval(original_switch_interval)
        for cloud_database in TARGET_MANAGER.cloud_databases:
            TARGET_MANAGER.remove_cloud_database(
                cloud_database=cloud_database,
            )


def _create_database(*, base_url: str) -> CloudDatabase:
    """Create a cloud database in the target manager."""
    database = CloudDatabase()
    response = requests.post(
        url=f"{base_url}/cloud_databases",
        json=database.to_dict(),
        timeout=30,
    )
    assert response.status_code == HTTPStatus.CREATED
    return database


def _create_target(
    *,
    session: requests.Session,
    base_url: str,
    database: CloudDatabase,
    image_base64: str,
) -> requests.Response:
    """Create a target in a given cloud database."""
    return session.post(
        url=f"{base_url}/cloud_databases/{database.database_name}/targets",
        json={
            "name": uuid.uuid4().hex,
            "width": 1,
            "image_base64": image_base64,
            "active_flag": True,
            "processing_time_seconds": 0,
            "application_metadata": None,
            "target_id": uuid.uuid4().hex,
        },
        timeout=30,
    )


def _run_concurrently(
    *,
    writer: Callable[[requests.Session], list[requests.Response]],
    reader: Callable[[requests.Session], list[requests.Response]],
) -> list[requests.Response]:
    """Run writers and readers at the same time and return all responses.

    Args:
        writer: A callable which makes requests which change state.  This is
            called once in each writer thread, with a session of its own.
        reader: A callable which makes requests which read state.  This is
            called in each reader thread, with a session of its own, until
            every writer has finished.

    Returns:
        Every response made by the writers and the readers.
    """
    responses: list[requests.Response] = []
    writers_finished = threading.Event()

    def run_writer() -> None:
        """Collect the responses of one writer."""
        # ``list.extend`` is atomic, so it needs no lock of its own.
        with requests.Session() as session:
            responses.extend(writer(session))

    def run_reader() -> None:
        """Collect the responses of one reader until the writers
        finish.
        """
        with requests.Session() as session:
            while not writers_finished.is_set():
                responses.extend(reader(session))

    reader_threads = [
        threading.Thread(target=run_reader) for _ in range(_NUM_READER_THREADS)
    ]
    writer_threads = [
        threading.Thread(target=run_writer) for _ in range(_NUM_WRITER_THREADS)
    ]
    for thread in [*reader_threads, *writer_threads]:
        thread.start()
    for thread in writer_threads:
        thread.join()
    writers_finished.set()
    for thread in reader_threads:
        thread.join()

    return responses


def _list_databases(
    *,
    session: requests.Session,
    base_url: str,
) -> requests.Response:
    """List all cloud databases."""
    return session.get(url=f"{base_url}/cloud_databases", timeout=30)


class TestConcurrentRequests:
    """Tests for making multiple requests to the target manager at
    once.
    """

    @staticmethod
    def test_create_targets_while_listing_databases(
        *,
        target_manager_base_url: str,
        small_image_base64: str,
    ) -> None:
        """Adding targets while databases are listed does not error."""
        base_url = target_manager_base_url
        database = _create_database(base_url=base_url)
        with requests.Session() as setup_session:
            for _ in range(_NUM_EXISTING_TARGETS):
                _create_target(
                    session=setup_session,
                    base_url=base_url,
                    database=database,
                    image_base64=small_image_base64,
                )

        def writer(session: requests.Session) -> list[requests.Response]:
            """Add targets to the database."""
            return [
                _create_target(
                    session=session,
                    base_url=base_url,
                    database=database,
                    image_base64=small_image_base64,
                )
                for _ in range(_NUM_REQUESTS_PER_WRITER)
            ]

        def reader(session: requests.Session) -> list[requests.Response]:
            """List all cloud databases."""
            return [_list_databases(session=session, base_url=base_url)]

        responses = _run_concurrently(writer=writer, reader=reader)

        error_statuses = [
            response.status_code
            for response in responses
            if response.status_code not in {HTTPStatus.OK, HTTPStatus.CREATED}
        ]
        assert not error_statuses

        expected_num_targets = _NUM_EXISTING_TARGETS + (
            _NUM_WRITER_THREADS * _NUM_REQUESTS_PER_WRITER
        )
        (matching_database,) = {
            item
            for item in TARGET_MANAGER.cloud_databases
            if item.database_name == database.database_name
        }
        assert len(matching_database.targets) == expected_num_targets

    @staticmethod
    def test_update_targets_while_listing_databases(
        *,
        target_manager_base_url: str,
        small_image_base64: str,
    ) -> None:
        """No listing sees a database without a target which is
        updated.
        """
        base_url = target_manager_base_url
        database = _create_database(base_url=base_url)
        database_url = f"{base_url}/cloud_databases/{database.database_name}"
        target_ids = set[str]()
        with requests.Session() as setup_session:
            for _ in range(_NUM_EXISTING_TARGETS):
                response = _create_target(
                    session=setup_session,
                    base_url=base_url,
                    database=database,
                    image_base64=small_image_base64,
                )
                target_ids.add(response.json()["target_id"])

        target_ids_to_update = list(target_ids)[:_NUM_WRITER_THREADS]
        target_ids_to_update_lock = threading.Lock()

        def writer(session: requests.Session) -> list[requests.Response]:
            """Update one target repeatedly."""
            with target_ids_to_update_lock:
                target_id = target_ids_to_update.pop()
            return [
                session.put(
                    url=f"{database_url}/targets/{target_id}",
                    json={"name": uuid.uuid4().hex},
                    timeout=30,
                )
                for _ in range(_NUM_REQUESTS_PER_WRITER)
            ]

        def reader(session: requests.Session) -> list[requests.Response]:
            """List all cloud databases."""
            return [_list_databases(session=session, base_url=base_url)]

        responses = _run_concurrently(writer=writer, reader=reader)

        error_statuses = [
            response.status_code
            for response in responses
            if response.status_code != HTTPStatus.OK
        ]
        assert not error_statuses

        listings = [
            response.json()
            for response in responses
            if response.request.method == HTTPMethod.GET
        ]
        for listing in listings:
            (listed_database,) = [
                item
                for item in listing
                if item["database_name"] == database.database_name
            ]
            listed_target_ids = {
                target["target_id"] for target in listed_database["targets"]
            }
            assert listed_target_ids == target_ids
