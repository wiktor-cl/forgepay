.PHONY: install lint format type test unit integration migrate compose-up compose-down demo failure-demo

install:
	python -m pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

type:
	mypy libs services

test:
	pytest

unit:
	pytest tests/unit tests/contract tests/concurrency

integration:
	pytest -m integration

migrate:
	alembic upgrade head

compose-up:
	docker compose up --build

compose-down:
	docker compose down -v

demo:
	python scripts/demo.py

failure-demo:
	python scripts/failure_demo.py
