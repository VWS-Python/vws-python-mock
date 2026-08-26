"""Decorators for using the mock."""

import functools
import re
import time
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Self
from urllib.parse import urlparse

import requests
from beartype import BeartypeConf, beartype
from requests import PreparedRequest
from responses import RequestsMock

from mock_vws._mock_common import MissingSchemeError, RequestData
from mock_vws._requests_mock_server.mock_web_query_api import (
    MockVuforiaWebQueryAPI,
)
from mock_vws._requests_mock_server.mock_web_services_api import (
    MockVuforiaWebServicesAPI,
)
from mock_vws._respx_mock_server.decorators import start_respx_router
from mock_vws.cloud_query import CloudQueryFailureResponse
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.image_matchers import (
    ImageMatcher,
    StructuralSimilarityMatcher,
)
from mock_vws.model_target import (
    ModelTargetFailureResponse,
    ModelTargetGenerationFailure,
    ModelTargetGenerationWarning,
)
from mock_vws.target_manager import TargetManager
from mock_vws.target_raters import (
    BrisqueTargetTrackingRater,
    TargetTrackingRater,
)
from mock_vws.vumark import VuMarkGenerationFailure

if TYPE_CHECKING:
    import respx

_ResponseType = tuple[int, Mapping[str, str], str | bytes]
_MockCallback = Callable[[RequestData], _ResponseType]
_ResponsesCallback = Callable[[PreparedRequest], _ResponseType]

_STRUCTURAL_SIMILARITY_MATCHER = StructuralSimilarityMatcher()
_BRISQUE_TRACKING_RATER = BrisqueTargetTrackingRater()


@beartype(conf=BeartypeConf(is_pep484_tower=True))
@dataclass(eq=True, frozen=True, kw_only=True)
class _MockVWSOptions:
    """The options which configure a mock.

    These are everything a mock is given when it is created, as opposed to
    the databases and targets which it accumulates as it is used.
    """

    base_vws_url: str
    base_vwq_url: str
    cloud_query_failure_response: CloudQueryFailureResponse | None
    duplicate_match_checker: ImageMatcher
    query_match_checker: ImageMatcher
    processing_time_seconds: float
    model_target_generation_failure: ModelTargetGenerationFailure | None
    model_target_failure_response: ModelTargetFailureResponse | None
    model_target_generation_warning: ModelTargetGenerationWarning | None
    model_target_training_allowance_exceeded: bool
    target_tracking_rater: TargetTrackingRater
    real_http: bool
    response_delay_seconds: float
    sleep_fn: Callable[[float], None]
    vumark_generation_failure: VuMarkGenerationFailure | None


@beartype(conf=BeartypeConf(is_pep484_tower=True))
class MockVWS:
    """Route requests to Vuforia's Web Service APIs to fakes of those APIs.

    Works with both ``requests`` and ``httpx``.

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
        base_vwq_url: str = "https://cloudreco.vuforia.com",
        cloud_query_failure_response: CloudQueryFailureResponse | None = None,
        duplicate_match_checker: ImageMatcher = _STRUCTURAL_SIMILARITY_MATCHER,
        query_match_checker: ImageMatcher = _STRUCTURAL_SIMILARITY_MATCHER,
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
        target_tracking_rater: TargetTrackingRater = _BRISQUE_TRACKING_RATER,
        real_http: bool = False,
        response_delay_seconds: float = 0.0,
        sleep_fn: Callable[[float], None] = time.sleep,
        vumark_generation_failure: VuMarkGenerationFailure | None = None,
    ) -> None:
        """Route requests to Vuforia's Web Service APIs to fakes of those
        APIs.

        Works with both ``requests`` and ``httpx``.

        Args:
            real_http: Whether or not to forward requests to the real
                server if they are not handled by the mock.
                See
                https://requests-mock.readthedocs.io/en/latest/mocker.html#real-http-requests.
            processing_time_seconds: The number of seconds to process each
                image for.
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
            base_vwq_url: The base URL for the VWQ API.
            base_vws_url: The base URL for the VWS API.
            cloud_query_failure_response: A response to return for every Cloud
                Query request, bypassing normal request validation and image
                matching. By default, Cloud Query requests are handled
                normally.
            vumark_generation_failure: A failure to return for every VuMark
                generation request, bypassing normal request validation and
                instance generation. By default, VuMark generation requests
                are handled normally.
            query_match_checker: A callable which takes two image values and
                returns whether they will match in a query request.
            duplicate_match_checker: A callable which takes two image values
                and returns whether they are duplicates.
            target_tracking_rater: A callable for rating targets for tracking.
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

        for url in (base_vwq_url, base_vws_url):
            parse_result = urlparse(url=url)
            if not parse_result.scheme:
                raise MissingSchemeError(url=url)

        # The options are kept so that decorating a function can build an
        # equivalently configured set of fakes, with their own databases and
        # targets, for each call of that function.
        self._options = _MockVWSOptions(
            base_vws_url=base_vws_url,
            base_vwq_url=base_vwq_url,
            cloud_query_failure_response=cloud_query_failure_response,
            duplicate_match_checker=duplicate_match_checker,
            query_match_checker=query_match_checker,
            processing_time_seconds=float(processing_time_seconds),
            model_target_generation_failure=model_target_generation_failure,
            model_target_failure_response=model_target_failure_response,
            model_target_generation_warning=model_target_generation_warning,
            model_target_training_allowance_exceeded=(
                model_target_training_allowance_exceeded
            ),
            target_tracking_rater=target_tracking_rater,
            real_http=real_http,
            response_delay_seconds=response_delay_seconds,
            sleep_fn=sleep_fn,
            vumark_generation_failure=vumark_generation_failure,
        )
        # A mock can be started while it is already started, for example
        # when a decorated function calls another decorated function, so the
        # started mocks are kept as a stack.
        self._started: list[tuple[RequestsMock, respx.MockRouter]] = []
        self._added_cloud_databases: list[CloudDatabase] = []
        self._added_vumark_databases: list[VuMarkDatabase] = []
        self._target_manager = TargetManager()
        self._mock_vws_api, self._mock_vwq_api = self._build_apis(
            target_manager=self._target_manager,
        )

    def _build_apis(
        self,
        *,
        target_manager: TargetManager,
    ) -> tuple[MockVuforiaWebServicesAPI, MockVuforiaWebQueryAPI]:
        """Build fakes of the Vuforia APIs, backed by a target manager.

        Args:
            target_manager: The target manager which the fakes use.

        Returns:
            A fake of the VWS API and a fake of the VWQ API.
        """
        options = self._options
        mock_vws_api = MockVuforiaWebServicesAPI(
            target_manager=target_manager,
            base_vws_url=options.base_vws_url,
            processing_time_seconds=options.processing_time_seconds,
            model_target_generation_failure=(
                options.model_target_generation_failure
            ),
            model_target_failure_response=options.model_target_failure_response,
            model_target_generation_warning=(
                options.model_target_generation_warning
            ),
            model_target_training_allowance_exceeded=(
                options.model_target_training_allowance_exceeded
            ),
            duplicate_match_checker=options.duplicate_match_checker,
            target_tracking_rater=options.target_tracking_rater,
            vumark_generation_failure=options.vumark_generation_failure,
        )
        mock_vwq_api = MockVuforiaWebQueryAPI(
            target_manager=target_manager,
            query_match_checker=options.query_match_checker,
            failure_response=options.cloud_query_failure_response,
        )
        return mock_vws_api, mock_vwq_api

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
        original_mock_vwq_api = self._mock_vwq_api

        self._target_manager = TargetManager()
        self._mock_vws_api, self._mock_vwq_api = self._build_apis(
            target_manager=self._target_manager,
        )
        for cloud_database in self._added_cloud_databases:
            self._target_manager.add_cloud_database(
                cloud_database=cloud_database,
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
            self._mock_vwq_api = original_mock_vwq_api

    def add_cloud_database(self, cloud_database: CloudDatabase) -> None:
        """Add a cloud database.

        Args:
            cloud_database: The cloud database to add.

        Raises:
            ValueError: One of the given cloud database keys matches a key for
                an existing cloud database.
        """
        self._target_manager.add_cloud_database(
            cloud_database=cloud_database,
        )
        self._added_cloud_databases.append(cloud_database)

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
            # ``CloudDatabase`` equality includes the targets, which change
            # during the call, so the snapshots are held in a list rather
            # than in a dictionary keyed by database.
            #
            # Reading and writing the targets in a database is guarded by
            # the target manager's lock, as documented on that lock.
            with self._target_manager.lock:
                cloud_snapshots = [
                    (database, set(database.targets))
                    for database in self._added_cloud_databases
                ]
                vumark_snapshots = [
                    (database, set(database.vumark_targets))
                    for database in self._added_vumark_databases
                ]

            try:
                with self._fresh_state(), self:
                    return function(*args, **kwargs)
            finally:
                with self._target_manager.lock:
                    for cloud_database, cloud_targets in cloud_snapshots:
                        cloud_database.targets.clear()
                        cloud_database.targets.update(cloud_targets)
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
        """Wrap a callback to add a response delay."""

        def wrapped(
            request: PreparedRequest,
        ) -> _ResponseType:
            """Handle the response delay and timeout logic."""
            # req_kwargs is added dynamically by the responses
            # library onto PreparedRequest objects - it is not
            # in the requests type stubs.
            req_kwargs: dict[str, Any] = getattr(  # pylint: disable=bad-builtin
                request,
                "req_kwargs",
                {},
            )
            timeout: tuple[float, float] | float | int | None = req_kwargs.get(
                "timeout"
            )
            # requests allows timeout as a (connect, read)
            # tuple. The delay simulates server response
            # time, so compare against the read timeout.
            match timeout:
                case (_, int() | float() as read_timeout):
                    effective: float | None = float(read_timeout)
                case int() | float():
                    effective = float(timeout)
                case _:
                    effective = None

            if effective is not None and delay_seconds > effective:
                sleep_fn(effective)
                raise requests.exceptions.Timeout

            match request.body:
                case None:
                    body_bytes = b""
                case str() as raw_body:
                    body_bytes = raw_body.encode(encoding="utf-8")
                case _:
                    body_bytes = request.body

            path = request.path_url
            if base_path and path.startswith(base_path):
                path = path[len(base_path) :]

            request_data = RequestData(
                method=request.method or "",
                path=path,
                headers=dict(request.headers),
                body=body_bytes,
            )
            result = callback(request_data)
            sleep_fn(delay_seconds)
            return result

        return wrapped

    def __enter__(self) -> Self:
        """Start an instance of a Vuforia mock.

        Returns:
            ``self``.
        """
        mock = RequestsMock(assert_all_requests_are_fired=False)

        for api, base_url in (
            (self._mock_vws_api, self._options.base_vws_url),
            (self._mock_vwq_api, self._options.base_vwq_url),
        ):
            base_path = urlparse(url=base_url).path.rstrip("/")
            for route in api.routes:
                url_pattern = base_url.rstrip("/") + route.path_pattern + "$"
                compiled_url_pattern = re.compile(pattern=url_pattern)

                for http_method in route.http_methods:
                    original_callback = getattr(  # pylint: disable=bad-builtin
                        api,
                        route.route_name,
                    )
                    mock.add_callback(
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
            mock_vwq_api=self._mock_vwq_api,
            base_vws_url=self._options.base_vws_url,
            base_vwq_url=self._options.base_vwq_url,
            response_delay_seconds=self._options.response_delay_seconds,
            sleep_fn=self._options.sleep_fn,
            real_http=self._options.real_http,
        )

        self._started.append((mock, router))
        return self

    def __exit__(self, *exc: object) -> Literal[False]:
        """Stop the Vuforia mock.

        Returns:
            False
        """
        # __exit__ needs this to be passed in but vulture thinks that it is
        # unused, so we "use" it here.
        del exc

        mock, router = self._started.pop()
        mock.stop()
        router.stop()
        return False
