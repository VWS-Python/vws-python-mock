"""Run one test suite against several interchangeable backends.

A "backend" is one way of running the system which the tests exercise.
A suite might run against a real remote service, an in-memory fake of
that service, and the same fake behind an HTTP server, and assert the
same things about each. That is how a fake is kept honest.

Nothing in this module knows about Vuforia, and nothing in it may import
from ``mock_vws``. Backends are identified by members of any
:class:`~enum.Enum`: the member name gives the command line option which
deselects it, and the member value gives the ID which ``pytest`` shows
for it.

This module is a candidate for extraction as a ``pytest`` plugin. Keep
it free of anything which is specific to this project so that extracting
it stays a move rather than a rewrite.
"""

import contextlib
import functools
from collections.abc import Callable, Generator, Iterable, Sequence
from enum import Enum

import pytest

# ``pytest.fixture`` returns one of these, but ``pytest`` does not export
# the type.
# See https://github.com/pytest-dev/pytest/issues/14853.
from _pytest.fixtures import (  # pylint: disable=import-private-name
    FixtureFunctionDefinition,
)
from beartype import beartype


@beartype
def _skip_option(*, backend: Enum) -> str:
    """The command line option which deselects a backend.

    Args:
        backend: The backend to give the option for.

    Returns:
        The name of the option which deselects the given backend.
    """
    return f"--skip-{backend.name.lower()}"


@beartype
def add_skip_options(
    *,
    parser: pytest.Parser,
    backends: Iterable[Enum],
) -> None:
    """Add an option which deselects each backend.

    Call this from a ``pytest_addoption`` hook. Tests which use a
    deselected backend are skipped rather than deselected, so that a run
    which skips a backend still reports the tests which would have used
    it.

    Args:
        parser: The parser to add options to.
        backends: The backends to add options for.
    """
    for backend in backends:
        parser.addoption(
            _skip_option(backend=backend),
            action="store_true",
            default=False,
            help=f"Skip tests for {backend.value}",
        )


@beartype
def _backend_ids(*, backends: Iterable[Enum]) -> list[str]:
    """The IDs which ``pytest`` shows for a set of backends.

    Args:
        backends: The backends to give IDs for.

    Returns:
        The ID to show for each given backend.
    """
    return [str(object=backend.value) for backend in backends]


@beartype
@contextlib.contextmanager
def _running_backend(
    *,
    backend: Enum,
    config: pytest.Config,
    setup: Callable[[], Generator[None]],
) -> Generator[None]:
    """Set a backend up for the duration of a test.

    Args:
        backend: The backend to run the test against.
        config: The configuration to look for skip options in.
        setup: A generator function which sets the backend up, yields
            once while the test runs, and then tears it down. Bind any
            arguments it needs with :func:`functools.partial` before
            passing it in.

    Yields:
        ``None``, once the backend is set up.
    """
    if config.getoption(name=_skip_option(backend=backend)):
        pytest.skip()

    with contextlib.contextmanager(func=setup)():
        yield


@beartype
def backend_fixture(
    *,
    name: str,
    backends: Sequence[Enum],
    setup_for: Callable[..., Generator[None]],
) -> FixtureFunctionDefinition:
    """Make a fixture which runs each test once per backend.

    Args:
        name: The name which tests use to request the fixture.
        backends: The backends to run each test against.
        setup_for: A generator function which is called with the keyword
            arguments ``backend`` and ``request``. It sets that backend
            up, yields once while the test runs, and then tears it down.
            Anything else it needs comes from
            :meth:`~pytest.FixtureRequest.getfixturevalue`, because a
            fixture made here requests no fixtures but ``request``.

    Returns:
        A fixture which yields the backend which the test is running
        against.
    """

    @pytest.fixture(
        name=name,
        params=backends,
        ids=_backend_ids(backends=backends),
    )
    def _fixture(*, request: pytest.FixtureRequest) -> Generator[Enum]:
        """Run a test against one backend.

        Yields:
            The backend which the test is running against.
        """
        backend: Enum = request.param
        setup = functools.partial(setup_for, backend=backend, request=request)
        with _running_backend(
            backend=backend,
            config=request.config,
            setup=setup,
        ):
            yield backend

    return _fixture
