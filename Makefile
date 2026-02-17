.PHONY: help install install-dev dev test lint format format-check quality pre-commit clean docker-build docker-up docker-down docker-logs docker-restart deploy

help:
	@echo "🚀 Available targets:"
	@echo ""
	@echo "Setup:"
	@echo "  install        - Install production dependencies"
	@echo "  install-dev    - Install development dependencies"
	@echo ""
	@echo "Development:"
	@echo "  dev            - Run in development mode"
	@echo "  test           - Run tests"
	@echo ""
	@echo "Code Quality:"
	@echo "  format         - Format code with Black, isort, and Ruff"
	@echo "  format-check   - Check code formatting (CI mode)"
	@echo "  lint           - Run linters (Ruff, mypy)"
	@echo "  quality        - Run all code quality checks"
	@echo "  pre-commit     - Run pre-commit hooks on all files"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build   - Build Docker images"
	@echo "  docker-up      - Start services"
	@echo "  docker-down    - Stop services"
	@echo "  docker-logs    - View logs"
	@echo "  docker-restart - Restart services"
	@echo ""
	@echo "Deployment:"
	@echo "  deploy         - Deploy to production"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean          - Clean build artifacts and caches"

install:
	uv sync

install-dev:
	@echo "📦 Installing development dependencies..."
	uv pip install -r requirements-dev.txt
	pre-commit install
	@echo "✅ Development environment ready!"

dev:
	uv run uvicorn src.main_agent:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest tests/ -v

lint:
	@echo "🔍 Running Ruff linter..."
	ruff check .
	@echo "🔍 Running mypy type checker..."
	uv run mypy src/ || true

format:
	@echo "🎨 Formatting code with Black..."
	black .
	@echo "📦 Sorting imports with isort..."
	isort .
	@echo "🔧 Running Ruff auto-fix..."
	ruff check --fix .
	@echo "✅ Code formatted successfully!"

format-check:
	@echo "🔍 Checking code formatting..."
	black --check .
	isort --check .
	ruff check .
	@echo "✅ Code formatting is correct!"

quality: format-check lint
	@echo "✅ All code quality checks passed!"

pre-commit:
	@echo "🪝 Running pre-commit on all files..."
	pre-commit run --all-files
	@echo "✅ Pre-commit checks complete!"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache dist build *.egg-info

docker-build:
	docker compose build --no-cache

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs --tail 200

docker-restart:
	docker compose restart

deploy: docker-build
	docker compose up -d --force-recreate

begin:
	rm -f uv.lock && uv sync
	$(MAKE) docker-build
	$(MAKE) docker-up
	docker compose logs agent --tail 200

down-up:
	rm -f uv.lock && uv sync
	docker compose down
	docker compose build
	docker compose up -d
