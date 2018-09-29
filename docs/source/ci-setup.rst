Continuous Integration
======================

Tests are run on Travis CI.
The configuration for this is in :file:`.travis.yml`.

Travis CI is set up with secrets for connecting to Vuforia.
These variables include those from :file:`vuforia_secrets.env.example`.

To avoid hitting request quotas and to avoid conflicts when running multiple tests in parallel, we use multiple target databases.

Travis builds use a different credentials file depending on the build number.
For example, build ``2045.1`` will use a different credentials file to build ``2045.2``.
This should avoid conflicts, but in theory the same credentials file may be run across two Pull Request builds.
This may cause errors.

How to Set Travis CI Secrets
----------------------------

Create environment variable files for secrets:

.. code:: sh

    mkdir -p ci_secrets
    cp vuforia_secrets.env.example ci_secrets/vuforia_secrets_1.env
    cp vuforia_secrets.env.example ci_secrets/vuforia_secrets_2.env
    ...

Add Vuforia credentials for different target databases to the new files in the ``ci_secrets/`` directory.
Add as many credentials files as there are builds in the Travis matrix.
All credentials files can share the same credentials for an inactive database.

Install the Travis CLI:

.. code:: sh

    gem install travis --no-rdoc --no-ri

Add the encrypted secrets files to the repository and Travis CI:

.. code:: sh

    make update-secrets

Note that the `Travis CI documentation <https://docs.travis-ci.com/user/encrypting-files/#Caveat>`__ warns that this might not work on Windows.

