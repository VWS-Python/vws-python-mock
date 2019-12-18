|project|
=========

Mocking Vuforia
---------------

Requests made to Vuforia can be mocked.
Using the mock redirects requests to Vuforia made with `requests <https://pypi.org/project/requests/>`_ to an in-memory implementation.

.. code:: python

    import requests
    from mock_vws import MockVWS, VuforiaDatabase

    with MockVWS() as mock:
        database = VuforiaDatabase()
        mock.add_database(database=database)
        # This will use the Vuforia mock.
        requests.get('https://vws.vuforia.com/summary')

Reference
---------

.. toctree::
   :maxdepth: 3

   api-reference
   installation
   differences-to-vws
   versioning-and-api-stability
   contributing

.. toctree::
   :hidden:

   changelog
   release-process
   ci-setup
