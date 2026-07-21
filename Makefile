.PHONY: dev up down test lint typecheck check migrate

dev:
	uv run uvicorn queueboard.main:app --reload

up:
	docker compose up --build

down:
	docker compose down

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy

check: lint typecheck test

migrate:
	uv run alembic upgrade head
