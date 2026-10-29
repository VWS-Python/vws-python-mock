"""Decorators for using the mock."""

import functools
import re
import time
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from types import TracebackType
from typing import Literal, Self
from urllib.parse import urlparse

import respx
from beartype import BeartypeConf, beartype
from mock_response_delay.for_requests import delayed_responses_callback
from requests import PreparedRequest
from responses import RequestsMock

from mock_vws._httpx2_mock_server.decorators import (
    Httpx2Router,
    start_httpx2_router,
)
from mock_vws._mock_common import (
    MissingSchemeError,
    RequestData,
)
from mock_vws._requests_mock_server.mock_web_services_api import (
    MockVuforiaWebServicesAPI,
)
from mock_vws._respx_mock_server.decorators import start_respx_router
from mock_vws.database import VuMarkDatabase
from mock_vws.model_target import (
    ModelTargetFailureResponse,
    ModelTargetGenerationFailure,
    ModelTargetGenerationWarning,
)
from mock_vws.target_manager import TargetManager
from mock_vws.vumark import VuMarkGenerationFailure

_ResponseType = tuple[int, Mapping[str, str], str | bytes]
_MockCallback = Callable[[RequestData], _ResponseType]
_ResponsesCallback = Callable[[PreparedRequest], _ResponseType]


@beartype(conf=BeartypeConf(is_pep484_tower=True))
@dataclass(eq=True, frozen=True, kw_only=True)
class _MockVWSOptions:
    """The options which configure a mock.

    These are everything a mock is given when it is created, as opposed to
    the databases and targets which it accumulates as it is used.
    """

    base_vws_url: str
    processing_time_seconds: int | float
    model_target_generation_failure: ModelTargetGenerationFailure | None
    model_target_failure_response: ModelTargetFailureResponse | None
    model_target_generation_warning: ModelTargetGenerationWarning | None
    model_target_training_allowance_exceeded: bool
    real_http: bool
    response_delay_seconds: float
    sleep_fn: Callable[[float], None]
    vumark_generation_failure: VuMarkGenerationFailure | None


@beartype(conf=BeartypeConf(is_pep484_tower=True))
class MockVWS:
    """Route requests to Vuforia's Web Service APIs to fakes of those APIs.

    Works with ``requests``, ``httpx`` and ``httpx2``.

    An instance is usable as a context manager and as a decorator.

    A context manager block shares one set of databases and targets with
    every other use of the same instance, so state created in one ``with``
    block is still there in the next one.

    A decorated function instead gets its own databases and targets for the
    duration of each call. The databases added to the instance are available
    inside the call, and the targets created during the call are discarded
    when it returns, so decorated functions do not affect each other.
    """

    def __init__(
        self,
        *,
        base_vws_url: str = "https://vws.vuforia.com",
        processing_time_seconds: float = 2.0,
        model_target_generation_failure: (
            ModelTargetGenerationFailure | None
        ) = None,
        model_target_failure_response: (
            ModelTargetFailureResponse | None
        ) = None,
        model_target_generation_warning: (
            ModelTargetGenerationWarning | None
        ) = None,
        model_target_training_allowance_exceeded: bool = False,
        real_http: bool = False,
        response_delay_seconds: float = 0.0,
        sleep_fn: Callable[[float], None] = time.sleep,
        vumark_generation_failure: VuMarkGenerationFailure | None = None,
    ) -> None:
        """Route requests to Vuforia's Web Service APIs to fakes of those
        APIs.

        Works with ``requests``, ``httpx`` and ``httpx2``.

        Args:
            real_http: Whether or not to forward requests to the real
                server if they are not handled by the mock.
                See
                https://requests-mock.readthedocs.io/en/latest/mocker.html#real-http-requests.
            processing_time_seconds: The number of seconds to process each
                Model Target dataset for.
                In the real Vuforia Web Services, this is not deterministic.
            model_target_generation_failure: A failure to return after every
                Model Target dataset finishes processing. By default, Model
                Target datasets finish successfully.
            model_target_failure_response: A response to return for the
                selected Model Target dataset request phases, after OAuth2
                token acquisition and before normal request validation. By
                default, Model Target dataset requests are handled normally.
            model_target_generation_warning: A warning to return after every
                Model Target dataset finishes processing. By default, Model
                Target datasets finish without warnings. This cannot be
                combined with ``model_target_generation_failure``.
            model_target_training_allowance_exceeded: Whether Model Target
                dataset creation returns Vuforia's
                ``TRAINING_ALLOWANCE_EXCEEDED`` response. By default, creation
                is allowed.
            base_vws_url: The base URL for the VWS API.
            vumark_generation_failure: A failure to return for every VuMark
                generation request, bypassing normal request validation and
                instance generation. By default, VuMark generation requests
                are handled normally.
            response_delay_seconds: The number of seconds to delay each
                response by. This can be used to test timeout handling.
            sleep_fn: The function to use for sleeping during response
                delays. Defaults to ``time.sleep``. Inject a custom
                function to control virtual time in tests without
                monkey-patching.

        Raises:
            MissingSchemeError: There is no scheme in a given URL.
            ValueError: Both a Model Target generation failure and warning are
                configured.
        """
        if (
            model_target_generation_failure is not None
            and model_target_generation_warning is not None
        ):
            msg = (
                "Model Target generation failure and warning configurations "
                "are mutually exclusive"
            )
            raise ValueError(msg)

        for url in (base_vws_url,):
            parse_result = urlparse(url=url)
            if not bool(parse_result.scheme):
                raise MissingSchemeError(url=url)

        # The options are kept so that decorating a function can build an
        # equivalently configured set of fakes, with their own databases and
        # targets, for each call of that function.
        self._options = _MockVWSOptions(
            base_vws_url=base_vws_url,
            processing_time_seconds=processing_time_seconds,
            model_target_generation_failure=model_target_generation_failure,
            model_target_failure_response=model_target_failure_response,
            model_target_generation_warning=model_target_generation_warning,
            model_target_training_allowance_exceeded=(
                model_target_training_allowance_exceeded
            ),
            real_http=real_http,
            response_delay_seconds=response_delay_seconds,
            sleep_fn=sleep_fn,
            vumark_generation_failure=vumark_generation_failure,
        )
        # A mock can be started while it is already started, for example
        # when a decorated function calls another decorated function, so the
        # started mocks are kept as a stack.
        self._started: list[
            tuple[RequestsMock, respx.MockRouter, Httpx2Router]
        ] = []
        self._added_vumark_databases: list[VuMarkDatabase] = []
        self._target_manager = TargetManager()
        self._mock_vws_api = self._build_apis(
            target_manager=self._target_manager,
        )

    def _build_apis(
        self, *, target_manager: TargetManager
    ) -> MockVuforiaWebServicesAPI:
        """Build the retained API handlers backed by a target manager."""
        options = self._options
        return MockVuforiaWebServicesAPI(
            target_manager=target_manager,
            processing_time_seconds=options.processing_time_seconds,
            model_target_generation_failure=options.model_target_generation_failure,
            model_target_failure_response=options.model_target_failure_response,
            model_target_generation_warning=options.model_target_generation_warning,
            model_target_training_allowance_exceeded=options.model_target_training_allowance_exceeded,
            vumark_generation_failure=options.vumark_generation_failure,
        )

    @contextmanager
    def _fresh_state(self) -> Generator[None]:
        """Swap in databases and targets which are used only in this block.

        The databases added to this instance are added to the new state, and
        the state which was there before the block is back once it ends.

        Yields:
            ``None``.
        """
        original_target_manager = self._target_manager
        original_mock_vws_api = self._mock_vws_api

        self._target_manager = TargetManager()
        self._mock_vws_api = self._build_apis(
            target_manager=self._target_manager,
        )
        for vumark_database in self._added_vumark_databases:
            self._target_manager.add_vumark_database(
                vumark_database=vumark_database,
            )

        try:
            yield
        finally:
            self._target_manager = original_target_manager
            self._mock_vws_api = original_mock_vws_api

    def add_vumark_database(self, vumark_database: VuMarkDatabase) -> None:
        """Add a VuMark database.

        Args:
            vumark_database: The VuMark database to add.

        Raises:
            ValueError: One of the given database keys matches a key for
                an existing database.
        """
        self._target_manager.add_vumark_database(
            vumark_database=vumark_database,
        )
        self._added_vumark_databases.append(vumark_database)

    def __call__[**P, T](
        self,
        function: Callable[P, T],
    ) -> Callable[P, T]:
        """Wrap a function so that each call of it runs against the mock.

        Each call gets its own databases and targets, so that decorated
        functions do not affect each other. The databases added to this
        instance are available inside the call, and their targets are what
        they were before the call again once it returns.

        Args:
            function: The function to wrap.

        Returns:
            The wrapped function.
        """

        @functools.wraps(wrapped=function)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            """Run the given function against a mock of its own.

            Returns:
                The return value of the given function.
            """
            # The targets of a database are stored on the database object
            # itself, and that object belongs to the caller, so a new target
            # manager is not enough to isolate one call from the next. We
            # therefore put the targets back as they were afterwards.
            #
            # Reading and writing the targets in a database is guarded by
            # the target manager's lock, as documented on that lock.
            with self._target_manager.lock:
                vumark_snapshots = [
                    (database, set(database.vumark_targets))
                    for database in self._added_vumark_databases
                ]

            try:
                with self._fresh_state(), self:
                    return function(*args, **kwargs)
            finally:
                with self._target_manager.lock:
                    for vumark_database, vumark_targets in vumark_snapshots:
                        vumark_database.vumark_targets.clear()
                        vumark_database.vumark_targets.update(vumark_targets)

        return wrapper

    @staticmethod
    def _wrap_callback(
        callback: _MockCallback,
        delay_seconds: float,
        sleep_fn: Callable[[float], None],
        base_path: str,
    ) -> _ResponsesCallback:
        """Wrap a callback to add a response delay and timeout."""

        def respond(request: PreparedRequest) -> _ResponseType:
            """Give a request to the callback."""
            match request.body:
                case None:
                    body_bytes = b""
                case str() as raw_body:
                    body_bytes = raw_body.encode(encoding="utf-8")
                case _:
                    body_bytes = request.body

            path = request.path_url
            if len(base_path) > 0 and path.startswith(base_path):
                path = path[len(base_path) :]

            request_data = RequestData(
                method=request.method if request.method is not None else "",
                path=path,
                headers=dict(request.headers),
                body=body_bytes,
            )
            return callback(request_data)

        return delayed_responses_callback(
            callback=respond,
            delay_seconds=delay_seconds,
            sleep_fn=sleep_fn,
        )

    def __enter__(self) -> Self:
        """Start an instance of a Vuforia mock.

        Returns:
            ``self``.
        """
        mock = RequestsMock(assert_all_requests_are_fired=False)

        for api, base_url in (
            (self._mock_vws_api, self._options.base_vws_url),
        ):
            base_path = urlparse(url=base_url).path.rstrip("/")
            for route in api.routes:
                url_pattern = base_url.rstrip("/") + route.path_pattern + "$"
                compiled_url_pattern = re.compile(pattern=url_pattern)

                for http_method in route.http_methods:
                    original_callback = route.handler
                    _ = mock.add_callback(
                        method=http_method,
                        url=compiled_url_pattern,
                        callback=self._wrap_callback(
                            callback=original_callback,
                            delay_seconds=self._options.response_delay_seconds,
                            sleep_fn=self._options.sleep_fn,
                            base_path=base_path,
                        ),
                        content_type=None,
                    )

        if self._options.real_http:
            all_requests_pattern = re.compile(pattern=".*")
            mock.add_passthru(prefix=all_requests_pattern)

        mock.start()

        router = start_respx_router(
            mock_vws_api=self._mock_vws_api,
            base_vws_url=self._options.base_vws_url,
            response_delay_seconds=self._options.response_delay_seconds,
            sleep_fn=self._options.sleep_fn,
            real_http=self._options.real_http,
            using=None,
            make_connect_error=None,
            make_timeout_error=None,
        )

        httpx2_router = start_httpx2_router(
            mock_vws_api=self._mock_vws_api,
            base_vws_url=self._options.base_vws_url,
            response_delay_seconds=self._options.response_delay_seconds,
            sleep_fn=self._options.sleep_fn,
            real_http=self._options.real_http,
        )

        self._started.append((mock, router, httpx2_router))
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> Literal[False]:
        """Stop the Vuforia mock.

        Returns:
            False
        """
        mock, router, httpx2_router = self._started.pop()
        mock.stop()
        router.stop()
        httpx2_router.stop()
        return False
