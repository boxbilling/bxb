.PHONY: help install dev test test-cov lint format migrate run clean openapi

help:
	@echo "bxb - Open Source Billing Software"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Development:"
	@echo "  install     Install all dependencies"
	@echo "  dev         Run development server"
	@echo "  worker      Run worker server"
	@echo "  test        Run tests"
	@echo "  test-cov    Run tests with 100% coverage check"
	@echo "  lint        Run linters"
	@echo "  format      Format code"
	@echo "  openapi     Generate OpenAPI schema and sync frontend client"
	@echo ""
	@echo "Database:"
	@echo "  migrate     Run database migrations"
	@echo "  migration   Create new migration (NAME=xxx)"
	@echo ""
	@echo "Docker:"
	@echo "  up          Start all services"
	@echo "  down        Stop all services"
	@echo "  logs        View logs"

# Backend
install:
	cd backend && uv sync --group dev
	cd frontend && npm install

dev:
	cd backend && uv run fastapi dev app/main.py --port 8000

worker:
	cd backend && uv run arq app.worker.WorkerSettings

test:
	cd backend && uv run pytest tests/ -v

test-cov:
	cd backend && uv run pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=100

lint:
	cd backend && uv run ruff check app/ tests/
	cd backend && uv run mypy app/

format:
	cd backend && uv run ruff format app/ tests/
	cd backend && uv run ruff check --fix app/ tests/

# OpenAPI - Generate schema and sync frontend client (run before each commit)
openapi:
	cd backend && uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > ./openapi.json
	cd frontend && npm run generate-client

# Database
migrate:
	cd backend && uv run alembic upgrade head

migration:
	cd backend && uv run alembic revision --autogenerate -m "$(NAME)"

# Frontend
frontend-dev:
	cd frontend && pnpm dev

frontend-build:
	cd frontend && pnpm build

# Docker
up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

# Clean
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf backend/.coverage backend/coverage.xml backend/htmlcov 2>/dev/null || true
