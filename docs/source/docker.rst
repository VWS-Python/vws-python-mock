Running a server with Docker
============================

Running the mock
----------------

There are three containers required.
One container mocks the VWS services, one container mocks the VWQ services and one container provides a shared storage backend.

Each of these containers run their services on port 5000.

The VWS and VWQ containers must point to the storage container using the :envvar:`STORAGE_BACKEND` variable.

# TODO Get a mock running with instructions here.
# TODO: Section for building containers
# TODO: Env vars for the configuration of the VWS / VWQ
# - Describe which are required and which are optional
# TODO respjson for the JSON response of the create database thing

From pre-built containers
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: sh

   docker network create -d bridge vws-bridge-network

   docker run \
       -p 5000:5000 \
       --name vws-mock-storage \
       --network vws-bridge-network \
       adamtheturtle/vws-mock-storage

   docker run \
       -e STORAGE_BACKEND=vws-mock-storage:5000 \
       --network vws-bridge-network \
       adamtheturtle/vuforia-vws-mock

   docker run \
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

   (Optional)
   Default 0.2

.. envvar:: DELETION_RECOGNITION_SECONDS

   (Optional)
   Default 0.2

VWS container
~~~~~~~~~~~~~


.. envvar:: PROCESSING_TIME_SECONDS

   Default 0.2

Creating a database
-------------------

The storage container does not mock any Vuforia service but it provides some functionality which mimics the database creation featurew of the Vuforia target manager.

To add a database, make a request to the following endpoint against the storage container:

.. autoflask:: mock_vws._flask_server.storage:STORAGE_FLASK_APP
   :endpoints: create_database
