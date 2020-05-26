#!/bin/sh

# This file is inspired by the GitHub actions example at
# https://help.github.com/en/actions/configuring-and-managing-workflows/creating-and-storing-encrypted-secrets#limits-for-secrets

# Decrypt the file
mkdir "${HOME}"/secrets
# --batch to prevent interactive command
# --yes to assume "yes" for questions
gpg \
    --quiet \
    --batch \
    --yes \
    --decrypt \
    --passphrase="${LARGE_SECRET_PASSPHRASE}" \
    --output "${HOME}"/secrets/secrets.tar \
    "${ENCRYPTED_FILE}"
