.PHONY: black
black: env/.done
	env/bin/black .

.PHONY: isort
isort: env/.done
	env/bin/isort .

.PHONY: fmt
fmt: isort black

.PHONY: clean
clean:
	rm -rf env docs html .tox .eggs build

env/.done: requirements-dev.txt setup.py
	virtualenv -p python3 env
	env/bin/pip install -e .[flask,django]
	env/bin/pip install -r requirements-dev.txt
	env/bin/pip uninstall -y argparse  # we want to use the built-in version of argparse
	touch $@

env/bin/tox: env/.done
	env/bin/pip install "tox<4"

.PHONY: lint
lint: env/.done
	env/bin/flake8 .
	env/bin/black . --check
	env/bin/isort . --check

.PHONY: test
test: env/.done
	env/bin/pytest

.PHONY: tox
tox: env/bin/tox
	env/bin/tox
