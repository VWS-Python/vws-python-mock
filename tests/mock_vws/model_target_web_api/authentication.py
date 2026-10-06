"""Authentication inputs and token creation for Model Target API tests."""

from beartype import beartype

from tests.mock_vws.fixtures.model_target_prepared_requests import (
    credentials_for_backend,
    get_access_token,
)
from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend

VWS_HOST = "https://vws.vuforia.com"


MOCK_BEARER_TOKEN = (
    "eyJhbGciOiJtb2NrIn0."
    "eyJzY29wZSI6Im1vZGVsdGFyZ2V0cy5zdGFuZGFyZG1vZGVsdGFyZ2V0LmFsbCJ9."
    "c2lnbmF0dXJl"
)


@beartype
def access_token_for_backend(*, backend: VuforiaBackend) -> str:
    """Return a valid access token for the chosen backend."""
    credentials = credentials_for_backend(backend=backend)
    return get_access_token(credentials=credentials, backend=backend)
