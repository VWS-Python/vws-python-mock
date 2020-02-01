Running a server with Docker
============================

Running the mock
----------------

# TODO this won't work - we need some kind of storage backend thing

.. code:: sh

   docker run adamtheturtle/mock-vuforia-storage-backend -e VWS_MOCK_DATABASES=$(cat vws-mock-config.json)
   docker run adamtheturtle/mock-vws -e VWS_MOCK_DATABASES=$(cat vws-mock-config.json)
   docker run adamtheturtle/mock-vwq -e VWS_MOCK_DATABASES=$(cat vws-mock-config.json)

Configuration
-------------

The ``VWS_MOCK_DATABASES`` environment variable must be set to a JSON configuration which looks like:

.. code-block:: json

   [
     {
         "state": "working",
         "server_access_key": "my_server_access_key",
         "server_secret_key": "my_server_secret_key",
         "client_access_key": "my_client_access_key",
         "client_secret_key": "my_client_secret_key"
     },
     {
         "state": "inactive",
         "server_access_key": "my_server_access_key2",
         "server_secret_key": "my_server_secret_key2",
         "client_access_key": "my_client_access_key2",
         "client_secret_key": "my_client_secret_key2"
     }
   ]

TODO: Also processing time etc.

Ports
~~~~~

Using ``docker-compose``
------------------------
