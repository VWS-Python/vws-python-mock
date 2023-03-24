Continuous Integration
======================

Tests are run on GitHub Actions.
The configuration for this is in :file:`.github/workflows`.

CI is set up with secrets for connecting to Vuforia.
These variables include those from :file:`vuforia_secrets.env.example`.

To avoid hitting request quotas and to avoid conflicts when running multiple tests in parallel, we use multiple target databases.

CI builds use a different credentials file depending on the build configuration.
Within a workflow, this avoids conflicts.

How to set GitHub Actions secrets
---------------------------------

Create environment variable files for secrets:

.. prompt:: bash

   mkdir -p ci_secrets
   cp vuforia_secrets.env.example ci_secrets/vuforia_secrets_1.env
   cp vuforia_secrets.env.example ci_secrets/vuforia_secrets_2.env
   ...

Add Vuforia credentials for different target databases to the new files in the ``ci_secrets/`` directory.
Add at least as many credentials files as there are builds in the GitHub test matrix.
All credentials files can share the same credentials for an inactive database.

Choose a passphrase for the secrets.
In the GitHub repository > Settings > Secrets, add a secret with the name ``PASSPHRASE_FOR_VUFORIA_SECRETS`` and the chosen passphrase.

Add the encrypted secrets files to the repository:

.. prompt:: bash

   PASSPHRASE_FOR_VUFORIA_SECRETS=<CHOSEN_SECRET> make update-secrets
   git add secrets.tar.gpg
   git commit -m "Update secret archive"
   git push
