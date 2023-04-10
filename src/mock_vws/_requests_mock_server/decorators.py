"""
Decorators for using the mock.
"""

from __future__ import annotations

import re
import time
import uuid
from contextlib import ContextDecorator
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol
from urllib.parse import urljoin, urlparse

import docker
import requests
from docker.errors import BuildError
from requests_mock.mocker import Mocker

from mock_vws.image_matchers import (
    AverageHashMatcher,
    ImageMatcher,
)
from mock_vws.target_manager import TargetManager
from mock_vws.target_raters import BrisqueTargetTrackingRater

from .mock_web_query_api import MockVuforiaWebQueryAPI
from .mock_web_services_api import MockVuforiaWebServicesAPI

if TYPE_CHECKING:
    from mock_vws.database import VuforiaDatabase
    from mock_vws.target_raters import TargetTrackingRater


_AVERAGE_HASH_MATCHER = AverageHashMatcher(threshold=10)
_BRISQUE_TRACKING_RATER = BrisqueTargetTrackingRater()


# TODO: Add pickled-function Docker checkers
# - Or maybe instead, add a Docker checker that uses a container with a known
#   spec - and then create such a container with pickle
#   - First probably we need to make the AverageHashMatcher setting configurable
#   - Then, add a configurable option for an HTTP endpoint
#   - HTTP endpoint is for all backends... then not special case for Docker?
# TODO: Make backends choosable by users
# TODO: Make a backend for Docker
#   - Be careful with real_http
# TODO: Make a backend for real Vuforia
#   - Be careful with real_http
# TODO: Use the Docker backend in VWS-Python timeout tests
# TODO: Use backends in fixtures for e.g. --skip-real
# TODO: Add a reset method to the backends


# We do not cover this function because hitting particular branches depends on
# timing.
def _wait_for_flask_app_to_start(base_url: str) -> None:  # pragma: no cover
    """
    Wait for a server to start.

    Args:
        base_url: The base URL of the Flask app to wait for.
    """
    max_attempts = 10
    sleep_seconds = 0.5
    url = f"{base_url}/{uuid.uuid4().hex}"
    for _ in range(max_attempts):
        try:
            response = requests.get(url, timeout=30)
        except requests.exceptions.ConnectionError:
            time.sleep(sleep_seconds)
        else:
            if response.status_code in {
                HTTPStatus.NOT_FOUND,
                HTTPStatus.UNAUTHORIZED,
                HTTPStatus.FORBIDDEN,
            }:
                return
    error_message = (
        f"Could not connect to {url} after "
        f"{max_attempts * sleep_seconds} seconds."
    )
    raise RuntimeError(error_message)


class _MockBackend(Protocol):
    def add_database(self, database: VuforiaDatabase) -> None:
        ...

    def start(
        self,
        base_vws_url: str,
        base_vwq_url: str,
        duplicate_match_checker: ImageMatcher,
        query_match_checker: ImageMatcher,
        processing_time_seconds: int | float,
        query_recognizes_deletion_seconds: int | float,
        query_processes_deletion_seconds: int | float,
        target_tracking_rater: TargetTrackingRater,
        *,
        real_http: bool,
    ) -> None:
        ...

    def stop(self) -> None:
        ...


class _RequestsMockBackend:
    def __init__(self) -> None:
        self._mock: Mocker
        self._target_manager = TargetManager()

    def add_database(self, database: VuforiaDatabase) -> None:
        self._target_manager.add_database(database=database)

    def start(
        self,
        base_vws_url: str,
        base_vwq_url: str,
        duplicate_match_checker: ImageMatcher,
        query_match_checker: ImageMatcher,
        processing_time_seconds: int | float,
        query_recognizes_deletion_seconds: int | float,
        query_processes_deletion_seconds: int | float,
        target_tracking_rater: TargetTrackingRater,
        *,
        real_http: bool,
    ) -> None:
        mock_vws_api = MockVuforiaWebServicesAPI(
            target_manager=self._target_manager,
            processing_time_seconds=processing_time_seconds,
            duplicate_match_checker=duplicate_match_checker,
            target_tracking_rater=target_tracking_rater,
        )

        mock_vwq_api = MockVuforiaWebQueryAPI(
            target_manager=self._target_manager,
            query_processes_deletion_seconds=(
                query_processes_deletion_seconds
            ),
            query_recognizes_deletion_seconds=(
                query_recognizes_deletion_seconds
            ),
            query_match_checker=query_match_checker,
        )

        with Mocker(real_http=real_http) as mock:
            for vws_route in mock_vws_api.routes:
                url_pattern = urljoin(
                    base=base_vws_url,
                    url=f"{vws_route.path_pattern}$",
                )

                for vws_http_method in vws_route.http_methods:
                    mock.register_uri(
                        method=vws_http_method,
                        url=re.compile(url_pattern),
                        text=getattr(mock_vws_api, vws_route.route_name),
                    )

            for vwq_route in mock_vwq_api.routes:
                url_pattern = urljoin(
                    base=base_vwq_url,
                    url=f"{vwq_route.path_pattern}$",
                )

                for vwq_http_method in vwq_route.http_methods:
                    mock.register_uri(
                        method=vwq_http_method,
                        url=re.compile(url_pattern),
                        text=getattr(mock_vwq_api, vwq_route.route_name),
                    )

        self._mock = mock
        self._mock.start()

    def stop(self) -> None:
        self._mock.stop()


class _DockerMockBackend:
    def __init__(self) -> None:
        self._network: docker.models.networks.Network

    def add_database(self, database: VuforiaDatabase) -> None:
        ...

    def start(
        self,
        base_vws_url: str,
        base_vwq_url: str,
        duplicate_match_checker: ImageMatcher,
        query_match_checker: ImageMatcher,
        processing_time_seconds: int | float,
        query_recognizes_deletion_seconds: int | float,
        query_processes_deletion_seconds: int | float,
        target_tracking_rater: TargetTrackingRater,
        *,
        real_http: bool,
    ) -> None:
        client = docker.from_env()
        try:
            self._network = client.networks.create(
                name="test-vws-bridge-" + uuid.uuid4().hex,
                driver="bridge",
            )
        except docker.errors.NotFound:
            # On Windows the "bridge" network driver is not available and we use
            # the "nat" driver instead.
            self._network = client.networks.create(
                name="test-vws-bridge-" + uuid.uuid4().hex,
                driver="nat",
            )

        repository_root = Path(__file__).parent.parent.parent
        dockerfile_dir = (
            repository_root / "src/mock_vws/_flask_server/dockerfiles"
        )
        target_manager_dockerfile = (
            dockerfile_dir / "target_manager" / "Dockerfile"
        )
        vws_dockerfile = dockerfile_dir / "vws" / "Dockerfile"
        vwq_dockerfile = dockerfile_dir / "vwq" / "Dockerfile"

        random = uuid.uuid4().hex
        target_manager_tag = f"vws-mock-target-manager:latest-{random}"
        vws_tag = f"vws-mock-vws:latest-{random}"
        vwq_tag = f"vws-mock-vwq:latest-{random}"

        try:
            target_manager_image, _ = client.images.build(
                path=str(repository_root),
                dockerfile=str(target_manager_dockerfile),
                tag=target_manager_tag,
            )
        except BuildError as exc:
            full_log = "\n".join(
                [item["stream"] for item in exc.build_log if "stream" in item],
            )
            # If this assertion fails, it may be useful to look at the other
            # properties of ``exc``.
            if (
                "no matching manifest for windows/amd64" not in exc.msg
            ):  # pragma: no cover
                raise AssertionError(full_log) from exc
            reason = "We do not currently support using Windows containers."
            raise ValueError(reason) from exc

        vws_image, _ = client.images.build(
            path=str(repository_root),
            dockerfile=str(vws_dockerfile),
            tag=vws_tag,
        )
        vwq_image, _ = client.images.build(
            path=str(repository_root),
            dockerfile=str(vwq_dockerfile),
            tag=vwq_tag,
        )

        target_manager_container_name = "vws-mock-target-manager-" + random
        target_manager_internal_base_url = (
            f"http://{target_manager_container_name}:5000"
        )

        target_manager_container = client.containers.run(
            image=target_manager_image,
            detach=True,
            name=target_manager_container_name,
            publish_all_ports=True,
            network=self._network.name,
        )
        vws_container = client.containers.run(
            image=vws_image,
            detach=True,
            name="vws-mock-vws-" + random,
            publish_all_ports=True,
            network=self._network.name,
            environment={
                "TARGET_MANAGER_BASE_URL": target_manager_internal_base_url,
            },
        )
        vwq_container = client.containers.run(
            image=vwq_image,
            detach=True,
            name="vws-mock-vwq-" + random,
            publish_all_ports=True,
            network=self._network.name,
            environment={
                "TARGET_MANAGER_BASE_URL": target_manager_internal_base_url,
            },
        )

        for container in (
            target_manager_container,
            vws_container,
            vwq_container,
        ):
            container.reload()

        target_manager_port_attrs = target_manager_container.attrs[
            "NetworkSettings"
        ]["Ports"]
        task_manager_host_ip = target_manager_port_attrs["5000/tcp"][0][
            "HostIp"
        ]
        task_manager_host_port = target_manager_port_attrs["5000/tcp"][0][
            "HostPort"
        ]

        vws_port_attrs = vws_container.attrs["NetworkSettings"]["Ports"]
        vws_host_ip = vws_port_attrs["5000/tcp"][0]["HostIp"]
        vws_host_port = vws_port_attrs["5000/tcp"][0]["HostPort"]

        vwq_port_attrs = vwq_container.attrs["NetworkSettings"]["Ports"]
        vwq_host_ip = vwq_port_attrs["5000/tcp"][0]["HostIp"]
        vwq_host_port = vwq_port_attrs["5000/tcp"][0]["HostPort"]

        base_vws_url = f"http://{vws_host_ip}:{vws_host_port}"
        base_vwq_url = f"http://{vwq_host_ip}:{vwq_host_port}"
        base_task_manager_url = (
            f"http://{task_manager_host_ip}:{task_manager_host_port}"
        )

        for base_url in (base_vws_url, base_vwq_url, base_task_manager_url):
            _wait_for_flask_app_to_start(base_url=base_url)

    def stop(self) -> None:
        self._network.reload()
        for container in self._network.containers:
            self._network.disconnect(container=container)
            container.stop()
            container.remove()
        self._network.remove()


class MockVWS(ContextDecorator):
    """
    Route requests to Vuforia's Web Service APIs to fakes of those APIs.
    """

    def __init__(
        self,
        base_vws_url: str = "https://vws.vuforia.com",
        base_vwq_url: str = "https://cloudreco.vuforia.com",
        duplicate_match_checker: ImageMatcher = _AVERAGE_HASH_MATCHER,
        query_match_checker: ImageMatcher = _AVERAGE_HASH_MATCHER,
        processing_time_seconds: int | float = 2,
        query_recognizes_deletion_seconds: int | float = 2,
        query_processes_deletion_seconds: int | float = 3,
        target_tracking_rater: TargetTrackingRater = _BRISQUE_TRACKING_RATER,
        mock_backend: type[_MockBackend] = _RequestsMockBackend,
        *,
        real_http: bool = False,
    ) -> None:
        """
        Route requests to Vuforia's Web Service APIs to fakes of those APIs.

        Args:
            real_http: Whether or not to forward requests to the real
                server if they are not handled by the mock.
                See
                https://requests-mock.readthedocs.io/en/latest/mocker.html#real-http-requests.
            processing_time_seconds: The number of seconds to process each
                image for.
                In the real Vuforia Web Services, this is not deterministic.
            base_vwq_url: The base URL for the VWQ API.
            base_vws_url: The base URL for the VWS API.
            query_recognizes_deletion_seconds: The number
                of seconds after a target has been deleted that the query
                endpoint will still recognize the target for.
            query_processes_deletion_seconds: The number of
                seconds after a target deletion is recognized that the query
                endpoint will return a 500 response on a match.
            query_match_checker: A callable which takes two image values and
                returns whether they will match in a query request.
            duplicate_match_checker: A callable which takes two image values
                and returns whether they are duplicates.
            target_tracking_rater: A callable for rating targets for tracking.

        Raises:
            requests.exceptions.MissingSchema: There is no schema in a given
                URL.
        """
        breakpoint()
        super().__init__()
        self._backend = mock_backend()

        self._base_vws_url = base_vws_url
        self._base_vwq_url = base_vwq_url
        self._duplicate_match_checker = duplicate_match_checker
        self._query_match_checker = query_match_checker
        self._processing_time_seconds = processing_time_seconds
        self._query_recognizes_deletion_seconds = (
            query_recognizes_deletion_seconds
        )
        self._query_processes_deletion_seconds = (
            query_processes_deletion_seconds
        )
        self._target_tracking_rater = target_tracking_rater
        self._real_http = real_http

        missing_scheme_error = (
            'Invalid URL "{url}": No scheme supplied. '
            'Perhaps you meant "https://{url}".'
        )
        for url in (base_vwq_url, base_vws_url):
            parse_result = urlparse(url=url)
            if not parse_result.scheme:
                error = missing_scheme_error.format(url=url)
                raise requests.exceptions.MissingSchema(error)

    def add_database(self, database: VuforiaDatabase) -> None:
        """
        Add a cloud database.

        Args:
            database: The database to add.

        Raises:
            ValueError: One of the given database keys matches a key for an
                existing database.
        """
        self._backend.add_database(database=database)

    def __enter__(self) -> MockVWS:
        """
        Start an instance of a Vuforia mock.

        Returns:
            ``self``.
        """
        self._backend.start(
            base_vws_url=self._base_vws_url,
            base_vwq_url=self._base_vwq_url,
            duplicate_match_checker=self._duplicate_match_checker,
            query_match_checker=self._query_match_checker,
            processing_time_seconds=self._processing_time_seconds,
            query_recognizes_deletion_seconds=self._query_recognizes_deletion_seconds,
            query_processes_deletion_seconds=self._query_processes_deletion_seconds,
            target_tracking_rater=self._target_tracking_rater,
            real_http=self._real_http,
        )
        return self

    def __exit__(self, *exc: tuple[None, None, None]) -> Literal[False]:
        """
        Stop the Vuforia mock.

        Returns:
            False
        """
        # __exit__ needs this to be passed in but vulture thinks that it is
        # unused, so we "use" it here.
        assert isinstance(exc, tuple)
        self._backend.stop()
        return False
