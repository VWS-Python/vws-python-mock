"""Health check for the Flask server."""

import http.client
import sys
from http import HTTPStatus

from beartype import beartype


@beartype
def flask_app_healthy(port: int) -> bool:
    """Check if the Flask app is healthy."""
    conn = http.client.HTTPConnection(host="localhost", port=port)
    try:
        conn.request(method="GET", url="/some-random-endpoint")
        response = conn.getresponse()
    # ``OSError`` covers ``TimeoutError``, ``ConnectionRefusedError`` and
    # ``socket.gaierror``.
    # ``ConnectionRefusedError`` is the expected error while the container is
    # starting up and nothing is yet listening on the port.
    except OSError, http.client.HTTPException:
        return False
    finally:
        conn.close()

    return response.status in {
        HTTPStatus.NOT_FOUND,
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
    }


if __name__ == "__main__":  # pragma: no cover
    sys.exit(int(not flask_app_healthy(port=5000)))
