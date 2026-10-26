.PHONY: help sync check check-fast check-full lint format typecheck test coverage fixture build

help:
	@printf '%s\n' \
		"make sync        Install the environment" \
		"make check       Fast checks plus tests" \
		"make check-fast  Lint, format, and types only" \
		"make check-full  Coverage, security, and fixture" \
		"make test        Run the unit tests" \
		"make coverage    Run tests with a coverage gate" \
		"make fixture     Run the weak fixture tests" \
		"make build       Build the package"

sync:
	uv sync

check: check-fast test

check-fast: lint typecheck

check-full: check coverage security fixture

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy src

test:
	uv run pytest -q

coverage:
	uv run pytest --cov=testproof --cov-fail-under=85

security:
	uv run bandit -q -r src -ll

fixture:
	cd fixtures/shop && uv run python -m pytest -q test_shipping.py

build:
	uv build
