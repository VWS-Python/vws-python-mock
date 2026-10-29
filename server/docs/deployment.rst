Container deployment
====================

Run the target manager and the VWS API as separate services on one network.
The target manager stores VuMark databases and Model Target datasets across VWS restarts.
The VWQ image and its service are no longer built or published.

Docker
------

Build the retained images from the repository root:

.. code-block:: console

   $ docker build -f server/Dockerfile --target target-manager -t vws-target-manager .
   $ docker build -f server/Dockerfile --target vws -t vws-api .
   $ docker network create vws-mock
   $ docker run -d --name vws-target-manager --network vws-mock -p 127.0.0.1:5005:5000 vws-target-manager
   $ docker run -d --name vws-api --network vws-mock -p 127.0.0.1:5006:5000 -e TARGET_MANAGER_BASE_URL=http://vws-target-manager:5000 vws-api

Wait for the containers' health checks before sending requests.
Use ``http://127.0.0.1:5005`` for target-manager setup and ``http://127.0.0.1:5006`` as the client's base VWS URL.
Create VuMark databases with ``POST /vumark_databases`` and templates with ``POST /vumark_databases/<database_name>/vumark_targets``.
Model Target requests use the VWS service's OAuth2 and dataset endpoints.

.. _apple-container-setup:

Creating containers with Apple container
----------------------------------------

This setup requires a Mac with Apple silicon and macOS 26 or later, Apple's ``container`` CLI 1.5.0 or later, and ``jq`` to read the container's address.
Install the runtime, start its services, and install the recommended Linux kernel:

.. code-block:: console

   $ brew install container jq
   $ container system start --disable-kernel-install
   $ container system kernel set --recommended

Allow Local Network access for ``container-runtime-linux`` when macOS prompts.
If requests to a published port reset, check this permission in System Settings → Privacy & Security → Local Network, then restart the container services.

Create a network and start the target manager first.
Read its IP address on that network for the VWS services to use:

.. code-block:: console

   $ container network create vws-bridge-network
   $ container run \
       --detach \
       --publish 127.0.0.1:5005:5000 \
       --name vuforia-target-manager-mock \
       --network vws-bridge-network \
       ghcr.io/vws-python/vuforia-target-manager-mock
   $ TARGET_MANAGER_IP="$(container inspect vuforia-target-manager-mock | jq -er '.[0].status.networks[0].ipv4Address | split("/")[0]')"
   $ export TARGET_MANAGER_BASE_URL="http://$TARGET_MANAGER_IP:5000"
   $ container run \
       --detach \
       --publish 127.0.0.1:5006:5000 \
       --name vuforia-vws-mock \
       --env "TARGET_MANAGER_BASE_URL=$TARGET_MANAGER_BASE_URL" \
       --network vws-bridge-network \
       ghcr.io/vws-python/vuforia-vws-mock

Using the target manager's IP avoids requiring DNS configuration for container names on this network.
The IP lookup removes the subnet suffix returned by ``container inspect``.
The scheme and container port are fixed, so the URL is constructed separately.
If you recreate the target manager, read its new address and recreate VWS with the updated ``TARGET_MANAGER_BASE_URL``.
The host ports match the Docker example, so the HTTP examples below work with either deployment.

Run each readiness probe until it exits successfully:

.. code-block:: console

   $ container exec vuforia-target-manager-mock python -m vws_mock_server.healthcheck
   $ container exec vuforia-vws-mock python -m vws_mock_server.healthcheck

To stop and remove this deployment:

.. code-block:: console

   $ container rm --force vuforia-vws-mock vuforia-target-manager-mock
   $ container network rm vws-bridge-network

State and cleanup
-----------------

State is held in memory in the target manager.
Restarting VWS preserves that state.
Restarting the target manager clears it.
Stop and remove the containers and their network after use.
