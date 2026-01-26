"""Health check for the Flask server."""

import http.client
import socket
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
    except (TimeoutError, http.client.HTTPException, socket.gaierror):
        return False
    finally:
        conn.close()

    return response.status in {
        HTTPStatus.NOT_FOUND,
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
    }


if __name__ == "__main__":
    sys.exit(int(not flask_app_healthy(port=5000)))
