"""Build and run the mock's three-service container deployment for
tests.
"""

import socket
import uuid
from collections.abc import Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

import docker
import pytest
import requests
from beartype import beartype
from docker.errors import BuildError, NotFound
from docker.models.containers import Container
from docker.models.images import Image
from docker.models.networks import Network
from pydantic import TypeAdapter
from pyprojroot import find_root, has_file
from tenacity import RetryError, retry
from tenacity.retry import retry_if_exception_type, retry_if_not_result
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed


@beartype
@dataclass(frozen=True, kw_only=True)
class MockDeployment:
    """The running mock containers and the URLs which reach them."""

    vws_container: Container
    base_vws_url: str
    base_vwq_url: str
    base_target_manager_url: str


@retry(
    wait=wait_fixed(wait=0.5),
    stop=stop_after_delay(max_delay=20),
    retry=retry_if_exception_type(
        exception_types=(requests.exceptions.ConnectionError, ValueError),
    ),
    reraise=True,
)
@beartype
def _poll_health_check(container: Container) -> None:
    """Poll a container until it reports a healthy status."""
    container.reload()
    health_status = container.health
    # In theory this might not be hit by coverage.
    # Let's keep it required by coverage for now.
    if health_status != "healthy":
        error_message = (
            f"Container {container.name} is not healthy: {health_status}"
        )
        raise ValueError(error_message)


@retry(
    wait=wait_fixed(wait=0.5),
    stop=stop_after_delay(max_delay=20),
    retry=(
        retry_if_not_result(predicate=bool)
        | retry_if_exception_type(
            exception_types=(requests.exceptions.RequestException,),
        )
    ),
    reraise=True,
)
@beartype
def _poll_http_health_check(*, base_url: str) -> bool:
    """Poll the published service URL until its HTTP probe succeeds."""
    with requests.get(
        url=f"{base_url}/some-random-endpoint",
        timeout=5,
    ) as response:
        return response.status_code in {
            HTTPStatus.NOT_FOUND,
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        }


@beartype
def wait_for_health_check(*, container: Container, base_url: str) -> None:
    """Wait for native Docker health and host-side HTTP readiness.

    On failure, augment the error with the container's logs and the
    Docker health check probe history so CI failures are easier to diagnose.
    """
    try:
        _poll_health_check(container=container)
        _ = _poll_http_health_check(base_url=base_url)
    # Healthy deployment tests do not enter this diagnostics path.
    except (
        ValueError,
        requests.exceptions.RequestException,
        RetryError,
    ) as exc:  # pragma: no cover
        container.reload()
        logs = container.logs().decode(errors="replace")
        state = TypeAdapter(type=dict[str, object]).validate_python(
            container.attrs["State"],
        )
        health = TypeAdapter(type=dict[str, object]).validate_python(
            state["Health"],
        )
        health_log = TypeAdapter(type=list[dict[str, object]]).validate_python(
            health.get("Log", []),
        )
        probes = "\n".join(
            f"  exit={entry.get('ExitCode')!r} "
            f"start={entry.get('Start')!r} end={entry.get('End')!r}\n"
            f"  output={entry.get('Output')!r}"
            for entry in health_log
        )
        error_message = (
            f"{exc}\n"
            f"--- container logs ({container.name}) ---\n"
            f"{logs}\n"
            f"--- healthcheck probes ({container.name}) ---\n"
            f"{probes}"
        )
        raise ValueError(error_message) from exc


@beartype
def _free_port() -> int:
    """Return a port which is free on the host.

    The VWS container publishes to a known port so that the base URL which
    it builds report download URLs from is known before it starts, and so
    that the URLs which reach it survive a restart of the container.

    Returns:
        A port which nothing was listening on when this was called.
    """
    with socket.socket(
        family=socket.AF_INET,
        type=socket.SOCK_STREAM,
    ) as sock:
        sock.bind(("127.0.0.1", 0))
        address = sock.getsockname()
        assert isinstance(address, tuple)
        assert isinstance(address[1], int)
        port: int = address[1]
        return port


@beartype
@retry(
    retry=retry_if_exception_type(exception_types=(KeyError, IndexError)),
    wait=wait_fixed(wait=0.1),
    stop=stop_after_delay(max_delay=10),
    reraise=True,
)
def _published_base_url(*, container: Container) -> str:
    """Return the host-reachable URL once Docker reports its port binding.

    Docker Desktop can return an empty binding list immediately after a
    container starts. Reloading on each bounded retry lets it finish
    publishing the port before the readiness probes use the URL.
    """
    container.reload()
    bindings = container.ports["5000/tcp"]
    assert bindings is not None
    host_ip = bindings[0]["HostIp"]
    host_port = bindings[0]["HostPort"]
    return f"http://{host_ip}:{host_port}"


@beartype
def _create_bridge_network(*, resources: ExitStack) -> Network:
    """Create a test network and register its removal immediately."""
    client = docker.from_env()
    name = "test-vws-bridge-" + uuid.uuid4().hex
    try:
        network = client.networks.create(name=name, driver="bridge")
    except NotFound:
        # On Windows the "bridge" network driver is not available and we use
        # the "nat" driver instead.
        network = client.networks.create(name=name, driver="nat")
    _ = resources.callback(network.remove)
    return network


@beartype
def _build_image(
    *,
    resources: ExitStack,
    repository_root: str,
    tag: str,
    target: str,
) -> Image:
    """Build one stage of the ``Dockerfile`` of the mock.

    Returns:
        The built image.
    """
    client = docker.from_env()
    dockerfile = f"{repository_root}/server/Dockerfile"
    try:
        image, _ = client.images.build(
            path=repository_root,
            dockerfile=dockerfile,
            tag=tag,
            target=target,
            rm=True,
            forcerm=True,
        )
    except BuildError as exc:
        full_log = "\n".join(
            [item["stream"] for item in exc.build_log if "stream" in item],
        )
        windows_message_substrings = (
            "no matching manifest for windows/amd64",
            "no matching manifest for windows(10.0.26100)/amd64",
        )
        if any(
            windows_message_substring in exc.msg
            for windows_message_substring in windows_message_substrings
        ):
            pytest.skip(
                reason="We do not currently support using Windows containers."
            )
        # Unexpected build failures terminate fixture setup.
        exc.add_note(full_log)  # pragma: no cover
        raise  # pragma: no cover
    # Remove this run's tag, preserving other runs which share a cached image.
    _ = resources.callback(client.images.remove, image=tag, force=True)
    return image


@beartype
def _start_container(*, resources: ExitStack, container: Container) -> None:
    """Register cleanup before starting an already-created container."""
    _ = resources.callback(container.remove, v=True, force=True)
    _ = resources.callback(container.stop)
    container.start()


@pytest.fixture(name="mock_deployment", scope="module")
def fixture_mock_deployment() -> Iterator[MockDeployment]:
    """Build the mock's images and run them as the Docker deployment does.

    The images are built and the containers are run once for all tests in
    this module, because building the images is the slowest thing these
    tests do.

    Yields:
        The running deployment.

    Resources are registered as they are created, including before setup
    yields. Containers are removed before the images and the network.
    """
    repository_root = str(
        object=find_root(
            criterion=has_file(file="uv.lock"),
            start=Path(__file__).resolve(),
        )
    )
    client = docker.from_env()
    random = uuid.uuid4().hex

    with ExitStack() as resources:
        custom_bridge_network = _create_bridge_network(resources=resources)

        target_manager_image = _build_image(
            resources=resources,
            repository_root=repository_root,
            tag=f"vws-mock-target-manager:latest-{random}",
            target="target-manager",
        )

        vwq_image = _build_image(
            resources=resources,
            repository_root=repository_root,
            tag=f"vws-mock-vwq:latest-{random}",
            target="vwq",
        )
        vws_image = _build_image(
            resources=resources,
            repository_root=repository_root,
            tag=f"vws-mock-vws:latest-{random}",
            target="vws",
        )

        target_manager_container_name = "vws-mock-target-manager-" + random
        target_manager_internal_base_url = (
            f"http://{target_manager_container_name}:5000"
        )
        vws_host_port = _free_port()
        base_vws_url = f"http://127.0.0.1:{vws_host_port}"

        target_manager_container = client.containers.create(
            image=target_manager_image,
            name=target_manager_container_name,
            publish_all_ports=True,
            network=custom_bridge_network.name,
        )
        _start_container(
            resources=resources, container=target_manager_container
        )
        vws_container = client.containers.create(
            image=vws_image,
            name="vws-mock-vws-" + random,
            ports={"5000/tcp": ("127.0.0.1", vws_host_port)},
            network=custom_bridge_network.name,
            environment={
                "TARGET_MANAGER_BASE_URL": target_manager_internal_base_url,
                # Report download URLs are built from this, so the URLs which
                # the VWS container gives out reach it from the host.
                "VWS_BASE_URL": base_vws_url,
            },
        )
        _start_container(resources=resources, container=vws_container)
        vwq_container = client.containers.create(
            image=vwq_image,
            name="vws-mock-vwq-" + random,
            publish_all_ports=True,
            network=custom_bridge_network.name,
            environment={
                "TARGET_MANAGER_BASE_URL": target_manager_internal_base_url,
            },
        )
        _start_container(resources=resources, container=vwq_container)

        for container in (
            target_manager_container,
            vws_container,
            vwq_container,
        ):
            wait_for_health_check(
                container=container,
                base_url=_published_base_url(container=container),
            )

        yield MockDeployment(
            vws_container=vws_container,
            base_vws_url=base_vws_url,
            base_vwq_url=_published_base_url(container=vwq_container),
            base_target_manager_url=_published_base_url(
                container=target_manager_container,
            ),
        )
