Running a server with Docker
============================

Running the mock
----------------

# TODO Get a mock running with instructions here.

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

Creating a database
-------------------

Make a POST request to the storage backend ``/databases`` with the keys:

* ``database_name``
* ``server_access_key``
* ``server_secret_key``
* ``client_access_key``
* ``client_secret_key``
* ``state`` (this can be ``"WORKING"`` or ``"PROJECT_INACTIVE"``)
