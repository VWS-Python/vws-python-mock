"""Tests for the health check used by the Docker images."""

import socket
import threading
from collections.abc import Generator
from contextlib import contextmanager
from http import HTTPStatus

import pytest
from beartype import beartype
from flask import Flask, Response
from werkzeug.serving import make_server

from mock_vws._flask_server.healthcheck import flask_app_healthy


@beartype
@contextmanager
def _app_responding_with(*, status: HTTPStatus) -> Generator[int]:
    """Serve an app which gives the given status, and yield its port."""
    app = Flask(import_name=__name__, static_folder=None)

    @beartype
    def _respond(_path: str) -> Response:
        """Respond with the given status and an empty body."""
        return Response(status=status)

    app.add_url_rule(rule="/<path:_path>", view_func=_respond)

    server = make_server(host="localhost", port=0, app=app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        thread.join()


@beartype
def _unused_port() -> int:
    """Return a port with nothing listening on it."""
    with socket.socket() as sock:
        sock.bind(("localhost", 0))
        port: int = sock.getsockname()[1]
    return port


@beartype
def test_nothing_listening() -> None:
    """No server on the port means not healthy.

    This is the state during container start-up, before the app binds the
    port.
    """
    assert not flask_app_healthy(port=_unused_port())


@pytest.mark.parametrize(
    argnames="status",
    argvalues=[
        HTTPStatus.NOT_FOUND,
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
    ],
)
@beartype
def test_healthy(*, status: HTTPStatus) -> None:
    """An app which handles a request for an unknown endpoint is
    healthy.
    """
    with _app_responding_with(status=status) as port:
        assert flask_app_healthy(port=port)


@pytest.mark.parametrize(
    argnames="status",
    argvalues=[HTTPStatus.OK, HTTPStatus.INTERNAL_SERVER_ERROR],
)
@beartype
def test_unhealthy(*, status: HTTPStatus) -> None:
    """Any other status means not healthy."""
    with _app_responding_with(status=status) as port:
        assert not flask_app_healthy(port=port)
