"""Configuration, plugins and fixtures for `pytest`."""

import base64
import binascii
import io
import uuid

import pytest
from beartype import beartype
from vws import VWS, CloudRecoService
from vws.reports import TargetStatuses

from mock_vws.database import CloudDatabase
from tests.mock_vws.utils import Endpoint, ModelTargetEndpoint
from tests.mock_vws.utils.retries import RETRY_ON_TRANSIENT_VWS_FAILURE

# The number of targets to add before giving up on getting one which
# processes with a 'success' status.
_TARGET_SUCCESS_ATTEMPTS = 3

# `credentials` must be listed before modules that import from it.
# If listed later, those imports happen before pytest can register it for
# assertion rewriting, causing a PytestAssertRewriteWarning.
pytest_plugins = [
    "tests.mock_vws.fixtures.credentials",
    "tests.mock_vws.fixtures.prepared_requests",
    "tests.mock_vws.fixtures.vuforia_backends",
    # ``model_target_prepared_requests`` imports from
    # ``vuforia_backends``, so it must be listed after it.
    "tests.mock_vws.fixtures.model_target_prepared_requests",
]


@pytest.fixture(name="vws_client")
def fixture_vws_client(*, vuforia_database: CloudDatabase) -> VWS:
    """A VWS client for an active VWS database."""
    return VWS(
        server_access_key=vuforia_database.server_access_key,
        server_secret_key=vuforia_database.server_secret_key,
    )


@pytest.fixture
def cloud_reco_client(*, vuforia_database: CloudDatabase) -> CloudRecoService:
    """A query client for an active VWS database."""
    return CloudRecoService(
        client_access_key=vuforia_database.client_access_key,
        client_secret_key=vuforia_database.client_secret_key,
    )


@pytest.fixture(name="inactive_vws_client")
def fixture_inactive_vws_client(
    *,
    inactive_cloud_database: CloudDatabase,
) -> VWS:
    """A client for an inactive VWS database."""
    return VWS(
        server_access_key=inactive_cloud_database.server_access_key,
        server_secret_key=inactive_cloud_database.server_secret_key,
    )


@pytest.fixture
def inactive_cloud_reco_client(
    *,
    inactive_cloud_database: CloudDatabase,
) -> CloudRecoService:
    """A query client for an inactive VWS database."""
    return CloudRecoService(
        client_access_key=inactive_cloud_database.client_access_key,
        client_secret_key=inactive_cloud_database.client_secret_key,
    )


@beartype
@RETRY_ON_TRANSIENT_VWS_FAILURE
def _add_target(*, vws_client: VWS, image: io.BytesIO) -> str:
    """Add a target, which is then in the processing state.

    We retry on transient failures here because pytest-retry does not
    retry on exceptions raised in fixtures.

    See
    https://github.com/str0zzapreti/pytest-retry/issues/33.

    Returns:
        The ID of the added target.
    """
    return vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image,
        active_flag=True,
        application_metadata=None,
    )


@beartype
@RETRY_ON_TRANSIENT_VWS_FAILURE
def _add_target_which_processed_successfully(
    *,
    vws_client: VWS,
    image: io.BytesIO,
) -> str:
    """Add a target which finishes processing with a 'success' status.

    Real Vuforia sometimes rates the given image badly enough to give the
    target a 'failed' status, so we delete such a target and add another
    one.

    Returns:
        The ID of a target with a 'success' status.
    """
    for _ in range(_TARGET_SUCCESS_ATTEMPTS):
        target_id_ = _add_target(vws_client=vws_client, image=image)
        vws_client.wait_for_target_processed(target_id=target_id_)
        target_details = vws_client.get_target_record(target_id=target_id_)
        if target_details.status == TargetStatuses.SUCCESS:
            return target_id_
        # We do not cover the rest of this function because in most test
        # runs no target gets a 'failed' status.
        vws_client.delete_target(target_id=target_id_)  # pragma: no cover

    message = (  # pragma: no cover
        "No target processed with a 'success' status in "
        f"{_TARGET_SUCCESS_ATTEMPTS} attempts."
    )
    raise AssertionError(message)  # pragma: no cover


@pytest.fixture
def target_id(*, high_quality_image: io.BytesIO, vws_client: VWS) -> str:
    """Return the target ID of a target in the database which has finished
    processing with a 'success' status.

    We use ``high_quality_image`` rather than
    ``image_file_success_state_low_rating``. The latter is a randomly
    generated 5x5 image, and real Vuforia often gives such an image a
    'failed' status. No test which uses this fixture needs a low rating.
    """
    return _add_target_which_processed_successfully(
        vws_client=vws_client,
        image=high_quality_image,
    )


@pytest.fixture
def unprocessed_target_id(
    *,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
) -> str:
    """Return the target ID of a target which was just added to the
    database.

    The target is in the processing state, or it has just left it. Use
    this rather than ``target_id`` for tests which do not need a
    processed target, as waiting for processing is slow against real
    Vuforia.
    """
    return _add_target(vws_client=vws_client, image=high_quality_image)


@pytest.fixture(
    params=[
        "add_target",
        "database_summary",
        "delete_target",
        "get_duplicates",
        "get_target",
        "target_list",
        "target_summary",
        "update_target",
        "query",
        "vumark_generate_instance",
        "reco_counts_report",
    ],
)
def endpoint(*, request: pytest.FixtureRequest) -> Endpoint:
    """
    Return details of an endpoint for the Target API or the Query
    API.

    The reco counts report download endpoint is not included because it
    deliberately takes no authorization, standing in for a presigned URL, so
    the cross-cutting ``Authorization`` and ``Date`` header concerns do not
    apply to it.
    """
    endpoint_fixture: Endpoint = request.getfixturevalue(argname=request.param)
    return endpoint_fixture


@pytest.fixture(
    params=[
        "create_standard_dataset",
        "create_advanced_dataset",
        "standard_dataset_status",
        "advanced_dataset_status",
        "download_standard_dataset",
        "download_advanced_dataset",
        "delete_standard_dataset",
        "delete_advanced_dataset",
    ],
)
def model_target_endpoint(
    *,
    request: pytest.FixtureRequest,
) -> ModelTargetEndpoint:
    """Return details of an endpoint for the Model Target Web API.

    The OAuth2 token endpoint is not included because it takes HTTP Basic
    credentials rather than a bearer token, so the cross-cutting bearer
    token concerns do not apply to it.
    """
    endpoint_fixture: ModelTargetEndpoint = request.getfixturevalue(
        argname=request.param,
    )
    return endpoint_fixture


@pytest.fixture(
    params=[
        pytest.param(
            "abcde",
            id="Length is one more than a multiple of four.",
        ),
        pytest.param(
            # We choose XN because it is different when decoded then encoded:
            #
            #
            # prints ``XA==``.
            "XN",
            id="Length is two more than a multiple of four.",
        ),
        pytest.param(
            "XNA",
            id="Length is three more than a multiple of four.",
        ),
    ],
)
def not_base64_encoded_processable(*, request: pytest.FixtureRequest) -> str:
    """Return a string which is not decodable as base64 data, but Vuforia
    will
    respond as if this is valid base64 data.

    ``UNPROCESSABLE_ENTITY`` when this is given.
    """
    not_base64_encoded_string: str = request.param

    with pytest.raises(expected_exception=binascii.Error):
        base64.b64decode(s=not_base64_encoded_string, validate=True)

    return not_base64_encoded_string


@pytest.fixture(
    params=[
        pytest.param(
            'aaa"',
            id="Includes a character which is not a base64 digit.",
        ),
        pytest.param('"', id="Not a base64 character."),
    ],
)
def not_base64_encoded_not_processable(
    *,
    request: pytest.FixtureRequest,
) -> str:
    """
    Return a string which is not decodable as base64 data, and Vuforia
    will
    return an ``UNPROCESSABLE_ENTITY`` response when this is given.
    """
    not_base64_encoded_string: str = request.param

    with pytest.raises(expected_exception=binascii.Error):
        base64.b64decode(s=not_base64_encoded_string, validate=True)

    return not_base64_encoded_string
