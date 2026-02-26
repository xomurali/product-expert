.PHONY: build up down logs migrate seed ingest-sample test shell lint fmt clean reset help

# ── Configuration ─────────────────────────────────────────────────────
COMPOSE := docker compose
API_CONTAINER := product-expert-api
DB_CONTAINER := product-expert-db
ENV_FILE := .env

# Check if .env exists, create from example if not
$(shell test -f $(ENV_FILE) || cp .env.example $(ENV_FILE) 2>/dev/null)

# ── Docker ────────────────────────────────────────────────────────────

build: ## Build all containers
	$(COMPOSE) build

up: ## Start all services in background
	$(COMPOSE) up -d
	@echo "╔══════════════════════════════════════════╗"
	@echo "║  Product Expert System                   ║"
	@echo "║  Frontend:  http://localhost              ║"
	@echo "║  API:       http://localhost:8000          ║"
	@echo "║  API (via nginx): http://localhost/api/    ║"
	@echo "╚══════════════════════════════════════════╝"

up-dev: ## Start with live reload (mount source)
	$(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml up -d

down: ## Stop all services
	$(COMPOSE) down

restart: ## Restart all services
	$(COMPOSE) restart

logs: ## Follow API logs
	$(COMPOSE) logs -f api

logs-all: ## Follow all service logs
	$(COMPOSE) logs -f

status: ## Show service status
	$(COMPOSE) ps

# ── Database ──────────────────────────────────────────────────────────

migrate: ## Run Alembic migrations
	$(COMPOSE) exec api alembic upgrade head

migrate-generate: ## Generate new migration (usage: make migrate-generate MSG="add xyz")
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(MSG)"

migrate-downgrade: ## Rollback last migration
	$(COMPOSE) exec api alembic downgrade -1

seed: ## Seed brands, families, and spec registry
	$(COMPOSE) exec api python -c "\
		import asyncio; \
		from seed import seed_database; \
		asyncio.run(seed_database())"

db-shell: ## Open psql shell
	$(COMPOSE) exec postgres psql -U expert -d product_expert

db-dump: ## Dump database to backup file
	$(COMPOSE) exec postgres pg_dump -U expert product_expert > backup_$$(date +%Y%m%d_%H%M%S).sql

db-reset: ## Drop and recreate database (DESTRUCTIVE)
	@echo "⚠️  This will destroy all data. Press Ctrl+C to cancel..."
	@sleep 3
	$(COMPOSE) exec postgres psql -U expert -c "DROP DATABASE IF EXISTS product_expert;"
	$(COMPOSE) exec postgres psql -U expert -c "CREATE DATABASE product_expert;"
	$(COMPOSE) exec postgres psql -U expert -d product_expert -f /docker-entrypoint-initdb.d/01-schema.sql
	$(COMPOSE) exec postgres psql -U expert -d product_expert -f /docker-entrypoint-initdb.d/02-seed.sql

# ── Ingestion ─────────────────────────────────────────────────────────

ingest-sample: ## Ingest sample data sheets from ./data/
	@echo "Ingesting sample documents..."
	@for f in data/*.pdf data/*.txt data/*.md; do \
		if [ -f "$$f" ]; then \
			echo "  → $$f"; \
			curl -s -X POST http://localhost:8000/ingest \
				-H "X-API-Key: dev-key-001" \
				-F "file=@$$f" | python -m json.tool; \
		fi; \
	done
	@echo "Done."

ingest-file: ## Ingest a single file (usage: make ingest-file FILE=path/to/doc.pdf)
	curl -X POST http://localhost:8000/ingest \
		-H "X-API-Key: dev-key-001" \
		-F "file=@$(FILE)" | python -m json.tool

# ── Testing ───────────────────────────────────────────────────────────

test: ## Run pytest
	$(COMPOSE) exec api pytest -v --tb=short

test-cov: ## Run tests with coverage
	$(COMPOSE) exec api pytest -v --cov=. --cov-report=term-missing --cov-report=html

test-local: ## Run tests locally (no Docker)
	pytest -v --tb=short

# ── Code Quality ──────────────────────────────────────────────────────

lint: ## Run ruff linter
	ruff check .

fmt: ## Format code with ruff
	ruff format .

typecheck: ## Run mypy type checking
	mypy --ignore-missing-imports *.py

# ── Development ───────────────────────────────────────────────────────

shell: ## Open bash shell in API container
	$(COMPOSE) exec api /bin/bash

python-shell: ## Open Python REPL in API container
	$(COMPOSE) exec api python

redis-cli: ## Open Redis CLI
	$(COMPOSE) exec redis redis-cli

# ── Monitoring ────────────────────────────────────────────────────────

health: ## Check system health
	@curl -s http://localhost:8000/health | python -m json.tool

stats: ## Show system statistics
	@curl -s http://localhost:8000/stats \
		-H "X-API-Key: dev-key-001" | python -m json.tool

conflicts: ## List pending spec conflicts
	@curl -s http://localhost:8000/conflicts \
		-H "X-API-Key: dev-key-001" | python -m json.tool

# ── Cleanup ───────────────────────────────────────────────────────────

clean: ## Remove containers and images
	$(COMPOSE) down --rmi local --remove-orphans

reset: ## Full reset: remove volumes, rebuild (DESTRUCTIVE)
	@echo "⚠️  This will destroy ALL data. Press Ctrl+C to cancel..."
	@sleep 3
	$(COMPOSE) down -v --remove-orphans
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d

# ── Help ──────────────────────────────────────────────────────────────

help: ## Show this help message
	@echo "Product Expert System — Make Targets"
	@echo "═══════════════════════════════════════"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
