"""Tests for decorator through the `requests-mock` backend."""

import io
import uuid
from http import HTTPStatus

import httpx
import httpx2
import pytest
import requests
from vws import VWS, CloudRecoService, VuMarkService
from vws.reports import TargetStatuses
from vws.transports import HTTPXTransport
from vws.vumark_accept import VuMarkAccept
from vws_auth_tools import rfc_1123_date

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.target import VuMarkTarget
from tests.mock_vws.requests_mock.helpers import unused_local_url


def test_requests_are_mocked_only_within_the_function() -> None:
    """Requests to Vuforia are mocked within the decorated function,
    and
    they are not mocked once the decorated function has returned.
    """
    base_vws_url = unused_local_url()
    summary_url = base_vws_url + "/summary"

    @MockVWS(base_vws_url=base_vws_url)
    def make_request() -> requests.Response:
        """Make a request to the mocked VWS API."""
        return requests.get(
            url=summary_url,
            headers={
                "Date": rfc_1123_date(),
                "Authorization": "bad_auth_token",
            },
            data=b"",
            timeout=30,
        )

    response = make_request()
    assert response.status_code == HTTPStatus.BAD_REQUEST

    # Nothing is listening on the given address, so this shows that the
    # mocking stops when the decorated function returns.
    with pytest.raises(expected_exception=requests.exceptions.ConnectionError):
        _ = requests.get(url=summary_url, timeout=30)


def test_httpx_requests_are_mocked() -> None:
    """Requests made with ``httpx`` are mocked within the decorated
    function.
    """
    base_vws_url = unused_local_url()
    summary_url = base_vws_url + "/summary"

    @MockVWS(base_vws_url=base_vws_url)
    def make_request() -> httpx.Response:
        """Make a request to the mocked VWS API."""
        return httpx.get(
            url=summary_url,
            headers={
                "Date": rfc_1123_date(),
                "Authorization": "bad_auth_token",
            },
            timeout=30,
        )

    response = make_request()
    assert response.status_code == HTTPStatus.BAD_REQUEST

    with pytest.raises(expected_exception=httpx.ConnectError):
        _ = httpx.get(url=summary_url, timeout=30)


def test_httpx2_requests_are_mocked() -> None:
    """Requests made with ``httpx2`` are mocked within the decorated
    function.
    """
    base_vws_url = unused_local_url()
    summary_url = base_vws_url + "/summary"

    @MockVWS(base_vws_url=base_vws_url)
    def make_request() -> httpx2.Response:
        """Make a request to the mocked VWS API."""
        return httpx2.get(
            url=summary_url,
            headers={
                "Date": rfc_1123_date(),
                "Authorization": "bad_auth_token",
            },
            timeout=30,
        )

    response = make_request()
    assert response.status_code == HTTPStatus.BAD_REQUEST

    with pytest.raises(expected_exception=httpx2.ConnectError):
        _ = httpx2.get(url=summary_url, timeout=30)


def test_arguments_and_return_value() -> None:
    """Arguments are passed to the decorated function, and its return
    value is returned.
    """

    @MockVWS()
    def join(*parts: str, separator: str) -> str:
        """Join the given parts."""
        return separator.join(parts)

    assert join("a", "b", separator="-") == "a-b"


def test_function_metadata_is_preserved() -> None:
    """The decorated function keeps its name and docstring."""

    @MockVWS()
    def my_function() -> None:
        """My docstring."""

    assert my_function.__name__ == "my_function"
    assert my_function.__doc__ == "My docstring."


def test_databases_added_before_decorating() -> None:
    """Databases added to the mock are available within the decorated
    function.
    """
    database = CloudDatabase()
    mock = MockVWS()
    mock.add_cloud_database(cloud_database=database)

    @mock
    def get_database_name() -> str:
        """Get the name of the database from the mock."""
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        return vws_client.get_database_summary_report().name

    assert get_database_name() == database.database_name


def test_vumark_database_added_before_decorating() -> None:
    """VuMark databases are available within a decorated function."""
    vumark_target = VuMarkTarget(name="test-target")
    database = VuMarkDatabase(vumark_targets={vumark_target})
    mock = MockVWS()
    mock.add_vumark_database(vumark_database=database)

    @mock
    def generate_vumark_instance() -> bytes:
        """Generate a VuMark instance from the configured database."""
        client = VuMarkService(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        return client.generate_vumark_instance(
            target_id=vumark_target.target_id,
            instance_id=uuid.uuid4().hex,
            accept=VuMarkAccept.PNG,
        )

    assert generate_vumark_instance().startswith(b"\x89PNG")


def test_options_are_used(image_file_failed_state: io.BytesIO) -> None:
    """Options given to the mock are used within the decorated
    function.
    """
    database = CloudDatabase()
    mock = MockVWS(processing_time_seconds=0)
    mock.add_cloud_database(cloud_database=database)

    @mock
    def add_target() -> TargetStatuses:
        """Add a target and return its status immediately."""
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        target_id = vws_client.add_target(
            name="example",
            width=1,
            image=image_file_failed_state,
            active_flag=True,
            application_metadata=None,
        )
        return vws_client.get_target_record(target_id=target_id).status

    # The given processing time of zero seconds means that the target is
    # processed immediately.
    assert add_target() == TargetStatuses.FAILED


def test_vumark_targets_are_restored() -> None:
    """VuMark targets changed during a call of a decorated function
    are put back as they were afterwards, just as Cloud targets
    are.
    """
    vumark_target = VuMarkTarget(name="existing-target")
    database = VuMarkDatabase(vumark_targets={vumark_target})
    mock = MockVWS()
    mock.add_vumark_database(vumark_database=database)

    temporary_target = VuMarkTarget(name="temporary")

    @mock
    def add_temporary_target() -> None:
        """Add a target to the database object directly."""
        database.vumark_targets.add(temporary_target)
        assert database.vumark_targets == {
            vumark_target,
            temporary_target,
        }

    add_temporary_target()
    assert database.vumark_targets == {vumark_target}


def test_each_call_is_isolated(high_quality_image: io.BytesIO) -> None:
    """Each call of a decorated function has its own targets.

    Targets created by one call are not there in the next call, or in a
    call of another function decorated with the same instance.
    """
    database = CloudDatabase()
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )
    mock = MockVWS(processing_time_seconds=0)
    mock.add_cloud_database(cloud_database=database)

    @mock
    def add_one_target() -> None:
        """Add a target with a name used only once per call."""
        _ = vws_client.add_target(
            name="only-one",
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        assert len(vws_client.list_targets()) == 1

    @mock
    def count_targets() -> int:
        """Return the number of targets in the database."""
        return len(vws_client.list_targets())

    add_one_target()
    assert count_targets() == 0
    add_one_target()
    assert count_targets() == 0


def test_nested_calls(high_quality_image: io.BytesIO) -> None:
    """A decorated function can call another decorated function.

    The inner call starts from the targets which are there when it is
    called, and the targets it creates are gone once it has returned. The
    outer call keeps its own targets and its mocking.
    """
    database = CloudDatabase()
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )
    mock = MockVWS(processing_time_seconds=0)
    mock.add_cloud_database(cloud_database=database)

    @mock
    def add_inner_target() -> int:
        """Add a target and return the number of targets.

        Returns:
            The number of targets, including the one added here.
        """
        _ = vws_client.add_target(
            name="inner",
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        return len(vws_client.list_targets())

    @mock
    def add_outer_target() -> tuple[int, int]:
        """Add a target and make an inner call.

        Returns:
            The number of targets seen by the inner call, and the number
            of targets seen here once the inner call has returned.
        """
        _ = vws_client.add_target(
            name="outer",
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        return add_inner_target(), len(vws_client.list_targets())

    targets_seen_by_inner_call = 2
    inner_count, outer_count = add_outer_target()
    assert inner_count == targets_seen_by_inner_call
    assert outer_count == 1
    assert not bool(database.targets)


def test_database_targets_are_restored(
    high_quality_image: io.BytesIO,
) -> None:
    """A database is restored to the targets it had before a call.

    The targets can be inspected during the call, and they are what they
    were before the call again once it returns.
    """
    database = CloudDatabase()
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )
    mock = MockVWS(processing_time_seconds=0)
    mock.add_cloud_database(cloud_database=database)

    @mock
    def add_one_target() -> None:
        """Add a target and inspect it on the database object."""
        _ = vws_client.add_target(
            name="only-one",
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        (target,) = database.targets
        assert target.name == "only-one"

    add_one_target()
    assert not bool(database.targets)


def test_exception_restores_database_targets(
    high_quality_image: io.BytesIO,
) -> None:
    """The targets of a database are restored even when the decorated
    function raises.
    """
    database = CloudDatabase()
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )
    mock = MockVWS(processing_time_seconds=0)
    mock.add_cloud_database(cloud_database=database)

    @mock
    def add_one_target_then_raise() -> None:
        """Add a target and then raise an exception.

        Raises:
            ValueError: Always.
        """
        _ = vws_client.add_target(
            name="only-one",
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        message = "Something went wrong."
        raise ValueError(message)

    with pytest.raises(
        expected_exception=ValueError,
        match=r"^Something went wrong\.$",
    ):
        add_one_target_then_raise()

    assert not bool(database.targets)


def test_query(high_quality_image: io.BytesIO) -> None:
    """Query requests are mocked within the decorated function."""
    database = CloudDatabase()
    mock = MockVWS(processing_time_seconds=0)
    mock.add_cloud_database(cloud_database=database)

    @mock
    def query() -> tuple[str, list[str]]:
        """Add a target and query for it."""
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        target_id = vws_client.add_target(
            name="example",
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        vws_client.wait_for_target_processed(target_id=target_id)
        cloud_reco_client = CloudRecoService(
            client_access_key=database.client_access_key,
            client_secret_key=database.client_secret_key,
            transport=HTTPXTransport(),
        )
        matches = cloud_reco_client.query(image=high_quality_image)
        return target_id, [match.target_id for match in matches]

    added_target_id, matching_target_ids = query()
    assert matching_target_ids == [added_target_id]


def test_decorating_a_method() -> None:
    """It is possible to decorate a method."""
    database = CloudDatabase()
    mock = MockVWS()
    mock.add_cloud_database(cloud_database=database)

    class _Example:
        """A class with a decorated method."""

        @mock
        def get_database_name(self) -> str:
            """Get the name of the database from the mock."""
            assert self is not None
            vws_client = VWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
            )
            return vws_client.get_database_summary_report().name

    assert _Example().get_database_name() == database.database_name
