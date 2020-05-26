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


By default, an exception will be raised if any requests to unmocked addresses are made.

See :ref:`mock-api-reference` for details of what can be changed and how.
