PYTHON ?= python3
export PYTHONPATH := src

.PHONY: all lint test check

all: check

lint:
	ruff format --check src tests bin README.md
	ruff check src tests bin README.md

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

check: lint test
