PYTHON ?= python3.12

.PHONY: setup test demo lint image

setup:
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install -e '.[dev]'

test:
	PYTHONPATH=src .venv/bin/python -m pytest

lint:
	.venv/bin/python -m ruff check src tests examples

demo:
	PYTHONPATH=src $(PYTHON) -m healer --json demo

image:
	docker build -t spectre-healer:local .
