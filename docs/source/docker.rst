Running a server with Docker
============================

It is possible run a Mock VWS instance using Docker containers.

This allows you to run tests against a mock VWS instance regardless of the language or tooling you are using.

Running the mock
----------------

There are three containers required.
One container mocks the VWS services, one container mocks the VWQ services and one container provides a shared target manager backend.

Each of these containers run their services on port 5000.

The VWS and VWQ containers must point to the target manager container using the :envvar:`TARGET_MANAGER_BACKEND` variable.

.. _creating-containers:

Creating containers
^^^^^^^^^^^^^^^^^^^

.. prompt:: bash

   docker network create -d bridge vws-bridge-network
   docker run \
       --detach \
       --publish 5005:5000 \
       --name vuforia-target-manager-mock \
       --network vws-bridge-network \
       adamtheturtle/vuforia-target-manager-mock
   docker run \
       --detach \
       --publish 5006:5000 \
       -e TARGET_MANAGER_BACKEND=vuforia-target-manager-mock:5000 \
       --network vws-bridge-network \
       adamtheturtle/vuforia-vws-mock
   docker run \
       --detach \
       --publish 5007:5000 \
       -e TARGET_MANAGER_BACKEND=vuforia-target-manager-mock:5000 \
       --network vws-bridge-network \
       adamtheturtle/vuforia-vwq-mock


Adding a database to the mock target manager
--------------------------------------------

When using Vuforia Web Services, it is necessary to create a database on the `Target Manager`_.
This is a web interface which does not have an HTTP API.

To mimic this functionality, this mock provides a target manager container which has an HTTP API.

To add a database, make a request to the following endpoint against the target manager container:

.. autoflask:: mock_vws._flask_server.target_manager:TARGET_MANAGER_FLASK_APP
   :endpoints: create_database

For example, with the containers set up as in :ref:`creating-containers`, use ``curl``:

.. prompt:: bash $ auto

   $ curl --request POST \
     --header "Content-Type: application/json" \
     --data '{}' \
     '127.0.0.1:5005/databases'
   {
       "client_access_key": "2d61c1d17bb94694bee77c1f1f41e5d9",
       "client_secret_key": "b73f8170cf7d42728fa8ce66221ad147",
       "database_name": "e515df24ba944f43b8f7969bc98af107",
       "server_access_key": "cb1759871a504875ab5f96d6db5ff79b",
       "server_secret_key": "9b8533d912ad4aa79cb61b6ee197ece2",
       "state_name": "WORKING",
       "targets": []
   }

Deleting a database
-------------------

To delete a database use the following endpoint:

.. autoflask:: mock_vws._flask_server.target_manager:TARGET_MANAGER_FLASK_APP
   :endpoints: delete_database


.. _Target Manager: https://developer.vuforia.com/target-manager


Configuration options
---------------------

Required configuration
^^^^^^^^^^^^^^^^^^^^^^

.. envvar:: TARGET_MANAGER_BACKEND

   This is required by the VWS mock and the VWQ mock containers.
   This is the route to the target manager container from the other containers.

Optional configuration
^^^^^^^^^^^^^^^^^^^^^^

Target manager container
~~~~~~~~~~~~~~~~~~~~~~~~

.. envvar:: TARGET_RATER

   The rater to use for target tracking ratings.

   Options include:

   * ``brisque``: The rating is derived using the BRISQUE algorithm.
   * ``perfect``: The rating is always 5.
   * ``random``: The rating is random.

   Default: ``brisque``

Query container
~~~~~~~~~~~~~~~

.. envvar:: QUERY_IMAGE_MATCHER

   The matcher to use for the query endpoint.

   Options include:

   * ``exact``: The images must be exactly the same to match.
   * ``structural_similarity``: The images must have a similar structural similarity to match.

   Default: ``structural_similarity``

VWS container
~~~~~~~~~~~~~

.. envvar:: PROCESSING_TIME_SECONDS

   The number of seconds to process each image for.

   Default: ``2``

.. envvar:: DUPLICATES_IMAGE_MATCHER

   The matcher to use for the duplicates endpoint.

   Options include:

   * ``exact``: The images must be exactly the same to be duplicates.
   * ``structural_similarity``: The images must have a similar structural similarity to be duplicates.

   Default: ``structural_similarity``

Building images from source
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. prompt:: bash

   export REPOSITORY_ROOT=$PWD
   export DOCKERFILE=$REPOSITORY_ROOT/src/mock_vws/_flask_server/Dockerfile

   export TARGET_MANAGER_TAG=adamtheturtle/vuforia-target-manager-mock:latest
   export VWS_TAG=adamtheturtle/vuforia-vws-mock:latest
   export VWQ_TAG=adamtheturtle/vuforia-vwq-mock:latest

   docker buildx build $REPOSITORY_ROOT --file $DOCKERFILE --target target-manager --tag $TARGET_MANAGER_TAG
   docker buildx build $REPOSITORY_ROOT --file $DOCKERFILE --target vws --tag $VWS_TAG
   docker buildx build $REPOSITORY_ROOT --file $DOCKERFILE --target vwq --tag $VWQ_TAG
