VWS mock server
===============

This separately buildable project contains the VWS, VWQ and target-manager Flask services and their health probe.
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

Services
--------

Each service runs in its own container and listens on port 5000.
The service modules are ``vws_mock_server.vws``, ``vws_mock_server.vwq`` and ``vws_mock_server.target_manager``.
The published image names, host environment variables and three-service deployment remain unchanged.
Compatibility modules under ``mock_vws._flask_server`` forward to these implementations when the server extra is installed.

Health checks
-------------

The published images continue to probe the local service on port 5000:

.. code-block:: console

   $ python -m vws_mock_server.healthcheck

The probe accepts the existing unauthorized, forbidden and missing-route responses as healthy.
It fails on connection errors, timeouts and other HTTP statuses.

Development tests
-----------------

The server project owns its Flask, health-check and container deployment tests.
Run them from the workspace root:

.. code-block:: console

   $ uv run --group=dev pytest server/tests --skip-backend=real

The Docker tests build and start all three services and require a running Docker daemon.
For the Flask and health-check cases alone, add ``--skip-marker=requires_docker_build``.
The shared fixtures are loaded explicitly from the installed contract package.
Shared API assertions remain maintained in that package.

Building container images
-------------------------

From the workspace root, build the three service targets with the server's bake definition:

.. code-block:: console

   $ docker buildx bake --file server/docker-bake.hcl

The default group builds ``linux/amd64`` and ``linux/arm64`` images.
The ``VERSION`` variable selects the version tag alongside ``latest``.
The image names and service targets remain the same.

Deployment
----------

See the `deployment guide <docs/deployment.rst>`_ for Docker and Apple container commands and service configuration.
