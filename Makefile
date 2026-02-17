.PHONY: help install dev test lint format clean docker-build docker-up docker-down docker-logs docker-restart deploy

help:
	@echo "Available targets:"
	@echo "  install        - Install dependencies"
	@echo "  dev            - Run in development mode"
	@echo "  test           - Run tests"
	@echo "  lint           - Run linters"
	@echo "  format         - Format code"
	@echo "  clean          - Clean build artifacts"
	@echo "  docker-build   - Build Docker images"
	@echo "  docker-up      - Start services"
	@echo "  docker-down    - Stop services"
	@echo "  docker-logs    - View logs"
	@echo "  docker-restart - Restart services"
	@echo "  deploy         - Deploy to production"

install:
	uv sync

dev:
	uv run uvicorn src.main_agent:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check src/ tests/
	uv run mypy src/

format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

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
