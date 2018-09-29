|Build Status| |codecov| |Updates| |PyPI| |Documentation Status|

VWS Python Mock
===============

Python mock for the Vuforia Web Services (VWS) API and the Vuforia Web Query API.

Installation
------------

.. code:: sh

    pip3 install vws-python-mock

This requires Python 3.7+.
Get in touch with ``adamdangoor@gmail.com`` if you would like to use this with another language.

Mocking Vuforia
---------------

Requests made to Vuforia can be mocked.
Using the mock redirects requests to Vuforia made with ``requests`` to an in-memory implementation.

.. code:: python

    import requests
    from mock_vws import MockVWS

    with MockVWS():
        # This will use the Vuforia mock.
        requests.get('https://vws.vuforia.com/summary')

However, by default, an exception will be raised if any requests to unmocked addresses are made.

Full Documentation
------------------

See the `full documentation <https://vws-python-mock.readthedocs.io/en/latest>`__.
This includes details on how to use the mock, options, and details of the differences between the mock and the real Vuforia Web Services.


.. |Build Status| image:: https://travis-ci.com/adamtheturtle/vws-python-mock.svg?branch=master
   :target: https://travis-ci.com/adamtheturtle/vws-python-mock
.. |codecov| image:: https://codecov.io/gh/adamtheturtle/vws-python-mock/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/adamtheturtle/vws-python-mock
.. |Updates| image:: https://pyup.io/repos/github/adamtheturtle/vws-python-mock/shield.svg
   :target: https://pyup.io/repos/github/adamtheturtle/vws-python-mock/
.. |PyPI| image:: https://badge.fury.io/py/VWS-Python-Mock.svg
    :target: https://badge.fury.io/py/VWS-Python-Mock
.. |Documentation Status| image:: https://readthedocs.org/projects/vws-python-mock/badge/?version=latest
   :target: https://vws-python-mock.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status
