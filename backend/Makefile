.PHONY: \
	help install install-dev dev test test-deprecation verify-deprecation lint format format-check quality pre-commit clean context-docs context-docs-check backfill-question-categories backfill-inline-guard \
	docker-build docker-up docker-down docker-logs docker-restart deploy deploy-prod prod-up prod-down \
	local-validate prod-validate local-env-audit backend-env-audit local-setup-check localsetup localsetup-full local-up local-down local-logs \
	local-ps local-restart local-router-up local-monitoring-up local-geoip-up local-edge-up \
	begin down-up

MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
REPO_ROOT ?= $(abspath $(MAKEFILE_DIR)/..)
ROOT_ENV_FILE ?= $(REPO_ROOT)/.env
BACKEND_ENV_FILE ?= .env

COMPOSE_FILE ?= $(REPO_ROOT)/compose.yaml

COMPOSE_BASE = docker compose --project-directory $(REPO_ROOT) \
    --env-file $(ROOT_ENV_FILE) -f $(COMPOSE_FILE)

LOCAL_COMPOSE  = $(COMPOSE_BASE) --profile local
# compose.yaml defines no profiles — all services run unconditionally.
# PROD_COMPOSE is the single deployed surface (Cloudflare tunnel routes
# mft-agent.pruthvirajchavan.codes and mft-api.pruthvirajchavan.codes to
# the frontend-prod + agent containers).
PROD_COMPOSE   = $(COMPOSE_BASE)

# Legacy alias — older helper targets reference MAIN_COMPOSE.
MAIN_COMPOSE   = $(PROD_COMPOSE)

LOCAL_CORE_SERVICES = redis postgres mcp-local agent-local

help:
	@echo "Available targets:"
	@echo ""
	@echo "Setup:"
	@echo "  install             - Install production dependencies"
	@echo "  install-dev         - Install development dependencies"
	@echo ""
	@echo "Development:"
	@echo "  dev                 - Run API in development mode"
	@echo "  test                - Run test suite"
	@echo ""
	@echo "Code Quality:"
	@echo "  format              - Format code with Black, isort, and Ruff"
	@echo "  format-check        - Check code formatting (CI mode)"
	@echo "  lint                - Run linters (Ruff, mypy)"
	@echo "  quality             - Run all code quality checks"
	@echo "  pre-commit          - Run pre-commit hooks on all files"
	@echo "  context-docs        - Generate leaf `_context.md` files and root `_main_context.md`"
	@echo "  context-docs-check  - Verify context docs are up-to-date (CI mode)"
	@echo "  backfill-question-categories - Backfill canonical business categories on EvalTrace nodes"
	@echo "  backfill-inline-guard - Backfill canonical inline guard fields on EvalTrace nodes"
	@echo ""
	@echo "Docker / Deployed (prod only — single environment behind Cloudflare tunnel):"
	@echo "  docker-build        - Build images"
	@echo "  docker-up           - Start stack"
	@echo "  docker-down         - Stop stack"
	@echo "  docker-logs         - View logs"
	@echo "  docker-restart      - Restart stack"
	@echo "  deploy              - Force-recreate deployment"
	@echo "  deploy-prod         - Build + force-recreate prod stack"
	@echo "  prod-up / prod-down - Start / stop prod stack"
	@echo ""
	@echo "Local Stack:"
	@echo "  local-validate      - Validate local compose config"
	@echo "  prod-validate       - Validate prod compose config"
	@echo "  local-env-audit     - Detect duplicate keys in root .env (compose interpolation)"
	@echo "  backend-env-audit   - Detect duplicate keys in backend/.env (runtime env_file)"
	@echo "  local-setup-check   - Run setup profile checks against local stack"
	@echo "  localsetup          - Validate/start local core stack and run setup checks"
	@echo "  localsetup-full     - Run localsetup, then start router + monitoring + geoip + edge"
	@echo "  local-up            - Start local core services ($(LOCAL_CORE_SERVICES))"
	@echo "  local-down          - Stop local stack"
	@echo "  local-logs          - Tail local stack logs"
	@echo "  local-ps            - Show local stack container status"
	@echo "  local-restart       - Restart local core services"
	@echo "  local-router-up     - Enable router worker profile"
	@echo "  local-monitoring-up - Enable monitoring profile"
	@echo "  local-geoip-up      - Enable geoip updater profile"
	@echo "  local-edge-up       - Enable cloudflared edge profile"
	@echo ""
	@echo "Legacy Helpers:"
	@echo "  begin               - Re-sync lockfile, rebuild, and start main stack"
	@echo "  down-up             - Re-sync lockfile, restart main stack"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean               - Remove Python caches/build artifacts"

install:
	uv sync

install-dev:
	@echo "Installing development dependencies..."
	uv pip install -r requirements-dev.txt
	uv run python -m pre_commit install --config .pre-commit-config.yaml --install-hooks
	@echo "Development environment ready"

dev:
	uv run uvicorn src.main_agent:app --reload --host 0.0.0.0 --port 8000

test:
	uv run python -m pytest tests/ -v

test-deprecation:
	PYTHONWARNINGS='error::DeprecationWarning,error::PendingDeprecationWarning' uv run python -m pytest tests/ -v

# One-shot Milvus rebuild for the eval_results_emb collection. Only
# needed once per environment when the collection's field schema drifts
# from the embedder's metadata shape (see docstring of the script).
rebuild-eval-results-collection:
	uv run python -m scripts.rebuild_eval_results_collection

verify-deprecation: test-deprecation
	@echo "Deprecation verification passed"

backfill-question-categories:
	uv run python -m scripts.backfill_question_categories --apply --batch-size $${BATCH_SIZE:-500}

backfill-inline-guard:
	uv run python -m scripts.backfill_inline_guard_fields --apply --batch-size $${BATCH_SIZE:-500}

lint:
	@echo "Running Ruff linter..."
	ruff check .
	@echo "Running mypy type checker..."
	uv run mypy --explicit-package-bases --follow-imports=skip --ignore-missing-imports \
		src/agent_service/api/admin.py \
		src/agent_service/features/knowledge_base/repo.py \
		src/agent_service/features/knowledge_base/service.py \
		src/agent_service/features/knowledge_base/faq_pdf_parser.py \
		src/agent_service/security/admin_crypto.py \
		src/agent_service/security/admin_jwt.py \
		src/agent_service/security/password_hash.py \
		src/agent_service/security/admin_totp.py

format:
	@echo "Formatting code with Black..."
	black .
	@echo "Sorting imports with isort..."
	isort .
	@echo "Running Ruff auto-fix..."
	ruff check --fix .
	@echo "Code formatted successfully"

format-check:
	@echo "Checking code formatting..."
	black --check .
	isort --check .
	ruff check .
	@echo "Code formatting is correct"

quality: format-check lint
	@echo "All code quality checks passed"

pre-commit:
	@echo "Running pre-commit on all files..."
	uv run python -m pre_commit run --all-files
	@echo "Pre-commit checks complete"

context-docs:
	uv run python scripts/generate_context_docs.py

context-docs-check:
	uv run python scripts/generate_context_docs.py --check

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache dist build *.egg-info

# Main compose targets

docker-build:
	$(MAIN_COMPOSE) build --no-cache

docker-up:
	$(MAIN_COMPOSE) up -d

docker-down:
	$(MAIN_COMPOSE) down

docker-logs:
	$(MAIN_COMPOSE) logs --tail 200

docker-restart:
	$(MAIN_COMPOSE) restart

deploy: docker-build
	$(MAIN_COMPOSE) up -d --force-recreate

deploy-prod:
	$(PROD_COMPOSE) build --no-cache
	$(PROD_COMPOSE) up -d --force-recreate

prod-up:
	$(PROD_COMPOSE) up -d

prod-down:
	$(PROD_COMPOSE) down

# Local compose targets

local-validate:
	$(LOCAL_COMPOSE) config >/tmp/compose.local.rendered.yml
	@echo "Local compose config is valid"

prod-validate:
	$(PROD_COMPOSE) config >/tmp/compose.prod.rendered.yml
	@echo "Prod compose config is valid"

local-env-audit:
	@echo "Checking root .env for duplicate keys..."
	@awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/{print $$1}' $(ROOT_ENV_FILE) | sort | uniq -d | \
		awk '{print "Duplicate key:", $$0}' || true

backend-env-audit:
	@echo "Checking backend/.env for duplicate keys..."
	@awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/{print $$1}' $(BACKEND_ENV_FILE) | sort | uniq -d | \
		awk '{print "Duplicate key:", $$0}' || true

local-up:
	$(LOCAL_COMPOSE) up -d $(LOCAL_CORE_SERVICES)

local-router-up:
	$(LOCAL_COMPOSE) --profile router up -d router-worker-local

local-monitoring-up:
	$(LOCAL_COMPOSE) --profile monitoring up -d prometheus alertmanager grafana

local-geoip-up:
	$(LOCAL_COMPOSE) --profile geoip up -d geoip-updater-local

local-edge-up:
	$(LOCAL_COMPOSE) --profile edge up -d cloudflared-local

local-setup-check:
	$(LOCAL_COMPOSE) --profile setup run --no-deps --rm localsetup

localsetup: local-validate local-up local-setup-check
	@echo "Local core stack is up and setup checks passed"

localsetup-full: localsetup
	$(LOCAL_COMPOSE) --profile router --profile monitoring --profile geoip --profile edge up -d \
		router-worker-local prometheus alertmanager grafana geoip-updater-local cloudflared-local
	@echo "Local full stack is up"

local-down:
	$(LOCAL_COMPOSE) down

local-logs:
	$(LOCAL_COMPOSE) logs --tail 200

local-ps:
	$(LOCAL_COMPOSE) ps

local-restart:
	$(LOCAL_COMPOSE) restart redis postgres mcp-local agent-local

# Legacy helpers

begin:
	rm -f uv.lock && uv sync
	$(MAKE) docker-build
	$(MAKE) docker-up
	$(MAIN_COMPOSE) logs agent --tail 200

down-up:
	rm -f uv.lock && uv sync
	$(PROD_COMPOSE) down
	$(PROD_COMPOSE) build
	$(PROD_COMPOSE) up -d
