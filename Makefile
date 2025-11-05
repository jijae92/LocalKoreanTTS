.PHONY: install run lint test type coverage

install:
	poetry install

run:
	poetry run python -m localkoreantts.cli --text "샘플" --output sample/output.txt --dry-run

lint:
	poetry run ruff check src tests

type:
	poetry run mypy --strict src

test:
	poetry run pytest

coverage:
	poetry run pytest --cov=src --cov-report=term-missing --cov-fail-under=80
