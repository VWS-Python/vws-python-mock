VWS mock server
===============

This separately buildable project owns server code while it is prepared for extraction.
The health probe is migrated first.
The three Flask services follow in separate changes.
Shared models, validation and API behavior stay in ``vws-python-mock``.

Build and install
-----------------

Build the workspace wheels and install them together:

.. code-block:: console

   $ uv build --all-packages --wheel --out-dir dist
   $ uv pip install dist/*.whl

The initial server version is ``0.0.0``.
Build the server and core library from the same repository commit.
For a Git installation, use that revision and the ``server`` subdirectory for this project.
The core's ``server`` extra selects this package and Flask when they are available in the workspace or as built wheels.
The default core installation does not require Flask.

The server consumes public core models and ``mock_vws.server_api``.
Its runtime dependencies do not include the contract suite or test adapters.
Consumers load those development dependencies explicitly.

Health checks
-------------

The published images continue to probe the local service on port 5000:

.. code-block:: console

   $ python -m vws_mock_server.healthcheck

The probe accepts the existing unauthorized, forbidden and missing-route responses as healthy.
It fails on connection errors, timeouts and other HTTP statuses.
