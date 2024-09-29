SHELL := /bin/bash -euxo pipefail

# Treat Sphinx warnings as errors
SPHINXOPTS := -W

.PHONY: update-secrets
update-secrets:
    # After updating secrets, commit the new secrets.tar.gpg file.
	tar cvf secrets.tar ci_secrets/
	gpg --yes --batch --passphrase=${PASSPHRASE_FOR_VUFORIA_SECRETS} --symmetric --cipher-algo AES256 secrets.tar

.PHONY: docs
docs:
	make -C docs clean html SPHINXOPTS=$(SPHINXOPTS)

.PHONY: open-docs
open-docs:
	python -c 'import os, webbrowser; webbrowser.open("file://" + os.path.abspath("docs/build/html/index.html"))'
