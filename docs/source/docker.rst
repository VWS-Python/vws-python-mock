Running a server with Docker
============================


Running the mock
----------------

There are three containers required.
One container mocks the VWS services, one container mocks the VWQ services and one container provides a shared storage backend.

Each of these containers run their services on port 5000.

The VWS and VWQ containers must point to the storage container using the :envvar:`STORAGE_BACKEND` variable.

Building images from source
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. prompt:: bash

   export REPOSITORY_ROOT=$PWD
   export DOCKERFILE_DIR=$REPOSITORY_ROOT/src/mock_vws/_flask_server/dockerfiles
   export BASE_DOCKERFILE=$DOCKERFILE_DIR/base/Dockerfile
   export STORAGE_DOCKERFILE=$DOCKERFILE_DIR/storage/Dockerfile
   export VWS_DOCKERFILE=$DOCKERFILE_DIR/vws/Dockerfile
   export VWQ_DOCKERFILE=$DOCKERFILE_DIR/vwq/Dockerfile

   export BASE_TAG=vws-mock:base
   export STORAGE_TAG=adamtheturtle/vws-mock-storage:latest
   export VWS_TAG=adamtheturtle/vuforia-vws-mock:latest
   export VWQ_TAG=adamtheturtle/vuforia-vwq-mock:latest

   docker build $REPOSITORY_ROOT --file $BASE_DOCKERFILE --tag $BASE_TAG
   docker build $REPOSITORY_ROOT --file $STORAGE_DOCKERFILE --tag $STORAGE_TAG
   docker build $REPOSITORY_ROOT --file $VWS_DOCKERFILE --tag $VWS_TAG
   docker build $REPOSITORY_ROOT --file $VWQ_DOCKERFILE --tag $VWQ_TAG

.. _creating-containers:

Creating containers
^^^^^^^^^^^^^^^^^^^

.. prompt:: bash

   docker network create -d bridge vws-bridge-network
   docker run \
       --detach \
       --publish 5000:5000 \
       --name vws-mock-storage \
       --network vws-bridge-network \
       adamtheturtle/vws-mock-storage
   docker run \
       --detach \
       --publish 5001:5000 \
       -e STORAGE_BACKEND=vws-mock-storage:5000 \
       --network vws-bridge-network \
       adamtheturtle/vuforia-vws-mock
   docker run \
       --detach \
       --publish 5002:5000 \
       -e STORAGE_BACKEND=vws-mock-storage:5000 \
       --network vws-bridge-network \
       adamtheturtle/vuforia-vwq-mock

Configuration options
---------------------

Required configuration
^^^^^^^^^^^^^^^^^^^^^^

.. envvar:: STORAGE_BACKEND

   This is required by the VWS mock and the VWQ mock containers.
   This is the route to the storage container from the other containers.

Optional configuration
^^^^^^^^^^^^^^^^^^^^^^

Query container
~~~~~~~~~~~~~~~

.. envvar:: DELETION_PROCESSING_SECONDS

   The number of seconds after a target deletion is recognized that the
   query endpoint will return a 500 response on a match.

   Default 0.2

.. envvar:: DELETION_RECOGNITION_SECONDS

   The number of seconds after a target has been deleted that the query
   endpoint will still recognize the target for.

   Default 0.2

VWS container
~~~~~~~~~~~~~

.. envvar:: PROCESSING_TIME_SECONDS

   The number of seconds to process each image for.

   Default 0.2

Creating a database
-------------------

The storage container does not mock any Vuforia service but it provides some functionality which mimics the database creation featurew of the Vuforia target manager.

To add a database, make a request to the following endpoint against the storage container:

.. autoflask:: mock_vws._flask_server.storage:STORAGE_FLASK_APP
   :endpoints: create_database

For example, with the containers set up as in :ref:`creating-containers`, use ``curl``:

.. prompt:: bash

   curl --request POST \
     --header "Content-Type: application/json" \
     --data '{}' \
     '127.0.0.1:5000/databases'
