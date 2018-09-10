SHELL := /bin/bash -euxo pipefail

.PHONY: fix-yapf
fix-yapf:
	yapf \
	    --in-place \
		--recursive \
		--exclude versioneer.py \
		--exclude src/mock_vws/_version.py \
		--exclude build \
	    .

.PHONY: autoflake
autoflake:
	autoflake \
	    --in-place \
	    --recursive \
	    --remove-all-unused-imports \
	    --remove-unused-variables \
	    --expand-star-imports \
	    --exclude src/mock_vws/_version.py,versioneer.py \
	    .

.PHONY: lint
lint:
	check-manifest .
	pytest -vvv -x ci/custom_linters.py
	dodgy
	flake8 .
	isort --recursive --check-only
	mypy src/ tests/ ci/ admin
	pip-extra-reqs src/
	pip-missing-reqs src/
	pydocstyle
	pylint *.py src tests ci admin
	pyroma --min 10 .
	vulture . --min-confidence 100
	yapf \
		--diff \
		--recursive \
		--exclude versioneer.py \
		--exclude build \
		--exclude src/mock_vws/_version.py \
		.

.PHONY: fix-lint
fix-lint: fix-yapf autoflake
	isort --recursive --apply

.PHONY: update-secrets
update-secrets:
	tar cvf secrets.tar ci_secrets/
	travis encrypt-file --com secrets.tar --add --force
	git add secrets.tar.enc .travis.yml
	git commit -m 'Update secret archive [skip ci]'
	git push
