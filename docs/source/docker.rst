Running a server with Docker
============================

Running the mock
----------------

# TODO Get a mock running with instructions here.

From source
^^^^^^^^^^^

.. code:: sh

   docker build \
       --file src/mock_vws/_flask_server/Dockerfile \
       --tag vws-mock \
       .

   docker build \
       --file src/mock_vws/_flask_server/Dockerfile \
       --tag vws-storage \
       src/mock_vws/_flask_server/vws

   docker build \
       --file src/mock_vws/_flask_server/Dockerfile \
       --tag vws-storage \
       src/mock_vws/_flask_server/vwq

From pre-built containers
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: sh

   docker run vws-mock \
       --entrypoint src/mock_vws/_flask_server/vws/__init__.py
       -e 
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
