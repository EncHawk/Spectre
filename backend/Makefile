UV ?= uv

.PHONY: setup test demo lint image migrate serve

setup:
	$(UV) sync --all-extras

test:
	$(UV) run --all-extras python -m pytest

lint:
	$(UV) run --extra dev python -m ruff check src tests examples db

demo:
	$(UV) run python -m healer --json demo

image:
	docker build -t spectre-healer:local .

migrate:
	$(UV) run --env-file .env --extra control python db/migrate.py

serve:
	$(UV) run --env-file .env --extra control --extra openai --extra neatlogs python -m healer serve
