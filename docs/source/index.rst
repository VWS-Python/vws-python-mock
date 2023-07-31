|project|
=========

Mocking calls made to Vuforia with Python ``requests``
------------------------------------------------------

.. prompt:: bash

   pip3 install vws-python-mock

This requires Python |python-minimum-version|\+.

.. include:: basic-example.rst

Using Docker to mock calls to Vuforia from any language
-------------------------------------------------------

It is possible run a Mock VWS instance using Docker containers.

This allows you to run tests against a mock VWS instance regardless of the language or tooling you are using.

See :doc:`docker` for how to do this.

Reference
---------

.. toctree::
   :maxdepth: 3

   installation
   getting-started
   docker
   mock-api-reference
   differences-to-vws
   versioning-and-api-stability
   contributing

.. toctree::
   :hidden:

   changelog
   release-process
   ci-setup
