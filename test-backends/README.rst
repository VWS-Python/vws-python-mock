VWS mock test backends
======================

This development package supplies the core repository's explicit pytest adapter plugin.
It supports the in-memory mock, Flask in process and real Vuforia.
The shared contract package does not load it automatically.

Load ``vws_mock_test_backends.vuforia_backends`` with pytest's ``-p`` option.
Use ``--skip-backend=real`` for runs without Vuforia credentials.
The mock adapters generate synthetic credentials.
Real credentials are read from the environment or ``vuforia_secrets.env`` in the working directory.

Install this package, ``vws-mock-contract-tests`` and the core library from the same repository commit.
The initial adapter package version is ``0.0.0``.
Server repositories can provide their own adapter plugin instead of installing this package.
