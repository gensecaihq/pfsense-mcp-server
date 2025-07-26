# pfSense MCP Server Makefile
SHELL := /bin/bash
.PHONY: help build run stop clean test logs shell lint format security-scan

# Variables
VERSION ?= 2.0.0
DOCKER_REGISTRY ?= 
IMAGE_NAME ?= pfsense-mcp
FULL_IMAGE_NAME = $(if $(DOCKER_REGISTRY),$(DOCKER_REGISTRY)/$(IMAGE_NAME),$(IMAGE_NAME))

# Colors
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check-env: ## Check required environment variables
	@if [ ! -f .env ]; then \
		echo "$(RED)Error: .env file not found. Copy .env.example to .env and configure it.$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Environment file found$(NC)"

build: check-env ## Build Docker images
	@echo "$(YELLOW)Building pfSense MCP Server v$(VERSION)...$(NC)"
	@docker-compose build \
		--build-arg VERSION=$(VERSION) \
		--build-arg BUILD_DATE=$(shell date -u +'%Y-%m-%dT%H:%M:%SZ') \
		--build-arg VCS_REF=$(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
	@echo "$(GREEN)Build complete$(NC)"

run: check-env ## Run the application stack
	@echo "$(YELLOW)Starting pfSense MCP Server...$(NC)"
	@docker-compose up -d
	@echo "$(GREEN)Stack started. Waiting for services...$(NC)"
	@sleep 5
	@make health-check

run-dev: check-env ## Run in development mode
	@echo "$(YELLOW)Starting in development mode...$(NC)"
	@PRODUCTION=false docker-compose up

stop: ## Stop the application stack
	@echo "$(YELLOW)Stopping services...$(NC)"
	@docker-compose down
	@echo "$(GREEN)Services stopped$(NC)"

restart: stop run ## Restart the application stack

logs: ## View application logs
	@docker-compose logs -f pfsense-mcp

logs-all: ## View all service logs
	@docker-compose logs -f

shell: ## Open shell in MCP container
	@docker-compose exec pfsense-mcp /bin/bash

shell-root: ## Open root shell in MCP container
	@docker-compose exec -u root pfsense-mcp /bin/bash

health-check: ## Check health of all services
	@echo "$(YELLOW)Checking service health...$(NC)"
	@docker-compose ps
	@echo ""
	@curl -s http://localhost:8000/health | jq . || echo "$(RED)MCP Server health check failed$(NC)"
	@echo ""
	@docker-compose exec redis redis-cli --pass changeme ping || echo "$(RED)Redis health check failed$(NC)"
	@echo ""
	@docker-compose exec postgres pg_isready -U mcp || echo "$(RED)PostgreSQL health check failed$(NC)"

test: ## Run tests
	@echo "$(YELLOW)Running tests...$(NC)"
	@docker-compose exec pfsense-mcp pytest tests/ -v --cov=. --cov-report=term-missing

test-integration: ## Run integration tests
	@echo "$(YELLOW)Running integration tests...$(NC)"
	@docker-compose exec pfsense-mcp pytest tests/integration/ -v

lint: ## Run linting
	@echo "$(YELLOW)Running linters...$(NC)"
	@docker-compose exec pfsense-mcp ruff check .
	@docker-compose exec pfsense-mcp mypy .

format: ## Format code
	@echo "$(YELLOW)Formatting code...$(NC)"
	@docker-compose exec pfsense-mcp black .
	@docker-compose exec pfsense-mcp ruff check --fix .

security-scan: ## Run security scan
	@echo "$(YELLOW)Running security scan...$(NC)"
	@docker run --rm -v $(PWD):/src \
		aquasec/trivy fs --severity HIGH,CRITICAL /src

db-migrate: ## Run database migrations
	@echo "$(YELLOW)Running database migrations...$(NC)"
	@docker-compose exec pfsense-mcp alembic upgrade head

db-rollback: ## Rollback database migration
	@echo "$(YELLOW)Rolling back database migration...$(NC)"
	@docker-compose exec pfsense-mcp alembic downgrade -1

backup: ## Backup configuration and data
	@echo "$(YELLOW)Creating backup...$(NC)"
	@mkdir -p backups
	@tar -czf backups/backup-$(shell date +%Y%m%d-%H%M%S).tar.gz \
		config/ data/ .env
	@echo "$(GREEN)Backup created in backups/$(NC)"

restore: ## Restore from backup (BACKUP=filename)
	@if [ -z "$(BACKUP)" ]; then \
		echo "$(RED)Error: BACKUP variable required$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Restoring from $(BACKUP)...$(NC)"
	@tar -xzf backups/$(BACKUP)
	@echo "$(GREEN)Restore complete$(NC)"

clean: ## Clean up containers and volumes
	@echo "$(RED)Warning: This will delete all data!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v; \
		rm -rf data/ logs/; \
		echo "$(GREEN)Cleanup complete$(NC)"; \
	fi

push: ## Push image to registry
	@if [ -z "$(DOCKER_REGISTRY)" ]; then \
		echo "$(RED)Error: DOCKER_REGISTRY not set$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Pushing $(FULL_IMAGE_NAME):$(VERSION)...$(NC)"
	@docker tag $(IMAGE_NAME):$(VERSION) $(FULL_IMAGE_NAME):$(VERSION)
	@docker tag $(IMAGE_NAME):$(VERSION) $(FULL_IMAGE_NAME):latest
	@docker push $(FULL_IMAGE_NAME):$(VERSION)
	@docker push $(FULL_IMAGE_NAME):latest
	@echo "$(GREEN)Push complete$(NC)"

deploy: build push ## Build and deploy to registry
	@echo "$(GREEN)Deployment complete$(NC)"

metrics: ## View Prometheus metrics
	@open http://localhost:9091 || xdg-open http://localhost:9091

grafana: ## Open Grafana dashboard
	@open http://localhost:3000 || xdg-open http://localhost:3000

cli-mode: check-env ## Run in CLI mode for Claude Desktop
	@echo "$(YELLOW)Starting in CLI mode...$(NC)"
	@docker run -it --rm \
		--env-file .env \
		-e MCP_MODE=stdio \
		$(IMAGE_NAME):$(VERSION)

generate-certs: ## Generate self-signed certificates
	@echo "$(YELLOW)Generating self-signed certificates...$(NC)"
	@mkdir -p config/ssl
	@openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
		-keyout config/ssl/key.pem \
		-out config/ssl/cert.pem \
		-subj "/C=US/ST=State/L=City/O=Organization/CN=pfsense-mcp.local"
	@echo "$(GREEN)Certificates generated in config/ssl/$(NC)"

install-hooks: ## Install git hooks
	@echo "$(YELLOW)Installing git hooks...$(NC)"
	@pre-commit install
	@echo "$(GREEN)Git hooks installed$(NC)"

version: ## Show version
	@echo "pfSense MCP Server v$(VERSION)"