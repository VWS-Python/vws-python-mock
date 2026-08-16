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

.. code-block:: console

   $ mkdir -p ci_secrets
   $ cp vuforia_secrets.env.example ci_secrets/vuforia_secrets_0.env
   $ cp vuforia_secrets.env.example ci_secrets/vuforia_secrets_1.env
   $ ...

Populate every variable listed in :file:`vuforia_secrets.env.example`.
Each file needs distinct active Cloud database credentials so concurrent jobs
do not modify the same database. The files can share the inactive Cloud,
active and inactive VuMark, and Model Target credentials.
Add at least as many consecutively numbered files, starting at zero, as there
are builds in the GitHub test matrix.

Choose a passphrase for the secrets.
In the GitHub repository > Settings > Secrets, add a secret with the name ``PASSPHRASE_FOR_VUFORIA_SECRETS`` and the chosen passphrase.

Add the encrypted secrets files to the repository:

.. code-block:: console

   $ tar cvf secrets.tar ci_secrets
   $ gpg --yes --batch --passphrase="${PASSPHRASE_FOR_VUFORIA_SECRETS}" --symmetric --cipher-algo AES256 secrets.tar
   $ git add secrets.tar.gpg
   $ git commit -m "Update secret archive"
   $ git push
