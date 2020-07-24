|Build Status| |codecov| |PyPI| |Documentation Status|

VWS Python Mock
===============

Python mock for the Vuforia Web Services (VWS) API and the Vuforia Web Query API.

Installation
------------

.. code:: sh

    pip3 install vws-python-mock

This requires Python 3.8.5+.
Get in touch with ``adamdangoor@gmail.com`` if you would like to use this with another language.

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

By default, an exception will be raised if any requests to unmocked addresses are made.

Full Documentation
------------------

See the `full documentation <https://vws-python-mock.readthedocs.io/en/latest>`__.
This includes details on how to use the mock, options, and details of the differences between the mock and the real Vuforia Web Services.


.. |Build Status| image:: https://github.com/VWS-Python/vws-python-mock/workflows/CI/badge.svg
   :target: https://github.com/VWS-Python/vws-python-mock/actions
.. |codecov| image:: https://codecov.io/gh/VWS-Python/vws-python-mock/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/VWS-Python/vws-python-mock
.. |PyPI| image:: https://badge.fury.io/py/VWS-Python-Mock.svg
    :target: https://badge.fury.io/py/VWS-Python-Mock
.. |Documentation Status| image:: https://readthedocs.org/projects/vws-python-mock/badge/?version=latest
   :target: https://vws-python-mock.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status
