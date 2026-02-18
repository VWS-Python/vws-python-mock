|Build Status| |PyPI|

VWS Mock
========

.. contents::
   :local:

Mock for the Vuforia Web Services (VWS) API and the Vuforia Web Query API.

Mocking calls made to Vuforia with Python ``requests``
------------------------------------------------------

Using the mock redirects requests to Vuforia made with `requests`_ to an in-memory implementation.

.. code-block:: shell

    pip install vws-python-mock

This requires Python |minimum-python-version|\+.

.. code-block:: python

    """Make a request to the Vuforia Web Services API mock."""

    import requests

    from mock_vws import MockVWS
    from mock_vws.database import VuforiaDatabase

    with MockVWS() as mock:
        database = VuforiaDatabase()
        mock.add_database(database=database)
        # This will use the Vuforia mock.
        requests.get(url="https://vws.vuforia.com/summary", timeout=30)

By default, an exception will be raised if any requests to unmocked addresses are made.

.. _requests: https://pypi.org/project/requests/

Using Docker to mock calls to Vuforia from any language
-------------------------------------------------------

It is possible run a Mock VWS instance using Docker containers.

This allows you to run tests against a mock VWS instance regardless of the language or tooling you are using.

See the `the instructions <https://vws-python.github.io/vws-python-mock/docker.html>`__ for how to do this.

Full documentation
------------------

See the `full documentation <https://vws-python.github.io/vws-python-mock/>`__.
This includes details on how to use the mock, options, and details of the differences between the mock and the real Vuforia Web Services.


.. |Build Status| image:: https://github.com/VWS-Python/vws-python-mock/actions/workflows/test.yml/badge.svg?branch=main
   :target: https://github.com/VWS-Python/vws-python-mock/actions
.. |PyPI| image:: https://badge.fury.io/py/VWS-Python-Mock.svg
    :target: https://badge.fury.io/py/VWS-Python-Mock
.. |minimum-python-version| replace:: 3.14
