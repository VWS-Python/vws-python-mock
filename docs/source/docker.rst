Running a server with Docker
============================

Running the mock
----------------

# TODO Get a mock running with instructions here.
# TODO: Section for building containers
# TODO: Env vars for the configuration of the VWS / VWQ

From pre-built containers
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: sh

   docker run --publish-all vws-mock-storage
   docker run vws-mock \
       -e STORAGE_BACKEND=... \
       -e QUERY_PROCESSES_DELETION_SECONDS=...
   docker run \
       adamtheturtle/mock-vwq \
       -e STORAGE_BACKEND=... \
       -e QUERY_PROCESSES_DELETION_SECONDS=...

Configuration options
---------------------

Query container:

TODO

VWS container:

TODO

Creating a database
-------------------

The VWS and VWQ containers mock the Vuforia services as closely as possible.

The storage container does not mock any Vuforia service but it provides some functionality which mimics the database creation featurew of the Vuforia target manager.

To add a database, make a request to the following endpoint against the storage container:

.. autoflask:: mock_vws._flask_server.storage:STORAGE_FLASK_APP
   :endpoints: create_database
