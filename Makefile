env/.done: requirements-dev.txt setup.py
	virtualenv -p python3 env
	env/bin/pip install -e .[flask,django]
	env/bin/pip install -r requirements-dev.txt
	env/bin/pip uninstall -y argparse  # we want to use the built-in version of argparse
	touch $@

.PHONY: test
test: env/.done
	env/bin/python setup.py test

env/bin/tox: env/.done
	env/bin/pip install tox

.PHONY: tox
tox: env/bin/tox
	env/bin/tox

clean:
	rm -rf env docs html .tox .eggs build
