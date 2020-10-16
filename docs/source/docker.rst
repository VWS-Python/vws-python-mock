Running a server with Docker
============================

Running the mock
----------------

# TODO Get a mock running with instructions here.
# TODO: Custom network
# TODO: Section for building containers
# TODO: Env vars for the configuration of the VWS / VWQ
# - Describe which are required and which are optional
# TODO respjson for the JSON response of the create database thing

From pre-built containers
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: sh

   docker run --publish-all vws-mock-storage
   docker run vws-mock -e STORAGE_BACKEND=...
   docker run adamtheturtle/mock-vwq -e STORAGE_BACKEND=...

Configuration options
---------------------

.. envvar:: STORAGE_BACKEND

   This environment variable is needed by ...

Query container:


.. envvar:: DELETION_PROCESSING_SECONDS

   Address

.. envvar:: DELETION_RECOGNITION_SECONDS

   Address

TODO all of these

VWS container:


.. envvar:: PROCESSING_TIME_SECONDS

   Address

Creating a database
-------------------

The VWS and VWQ containers mock the Vuforia services as closely as possible.

The storage container does not mock any Vuforia service but it provides some functionality which mimics the database creation featurew of the Vuforia target manager.

To add a database, make a request to the following endpoint against the storage container:

.. autoflask:: mock_vws._flask_server.storage:STORAGE_FLASK_APP
   :endpoints: create_database
