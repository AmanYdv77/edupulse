# ==============================================================================
# EduPulse Development & Operations Makefile
# Note: Windows users without 'make' can run the underlying commands directly in PowerShell.
# ==============================================================================

.PHONY: help up down logs migrate test e2e lint fmt lock train-a fe-dev fe-test fe-build

help: ## Display this help message
	@echo "EduPulse Operations Commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Start the full containerized stack (web, worker, beat, postgres, redis instances)
	docker compose up --build -d

down: ## Stop and tear down all containerized services
	docker compose down

logs: ## Tail real-time logs from all running containers
	docker compose logs -f

migrate: ## Run Django database migrations inside container
	docker compose run --rm web python backend/manage.py migrate

test: ## Run local backend unit and integration test suite
	pytest -q

e2e: ## Run end-to-end browser tests via Playwright
	pytest -m e2e

lint: ## Run Ruff linter and Mypy static type analysis
	ruff check backend tests && mypy backend

fmt: ## Format Python and frontend codebases
	ruff format backend tests && cd frontend && npm run format

lock: ## Recompile and lock pip dependency requirements
	pip-compile requirements.in -o requirements.txt && pip-compile requirements-dev.in -o requirements-dev.txt

train-a: ## Train and register Model A (baseline model)
	docker compose --profile tools run --rm tools python backend/manage.py train_model_a

fe-dev: ## Start frontend Vite development server
	cd frontend && npm run dev

fe-test: ## Run frontend Vitest unit and component tests
	cd frontend && npm test

fe-build: ## Compile production React SPA bundle
	cd frontend && npm run build
