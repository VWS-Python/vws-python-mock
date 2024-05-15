# Make commands for linting

SHELL := /bin/bash -euxo pipefail

.PHONY: linkcheck
linkcheck:
	$(MAKE) -C docs/ linkcheck SPHINXOPTS=$(SPHINXOPTS)

.PHONY: pyproject-fmt
pyproject-fmt:
	pyproject-fmt --check pyproject.toml

.PHONY: fix-pyproject-fmt
fix-pyproject-fmt:
	pyproject-fmt pyproject.toml

.PHONY: spelling
spelling:
	$(MAKE) -C docs/ spelling SPHINXOPTS=$(SPHINXOPTS)
