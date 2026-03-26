# pfSense MCP Server Makefile
SHELL := /bin/bash
.PHONY: help build run stop clean test lint format logs shell

# Variables
VERSION ?= 1.0.0
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

build: ## Build Docker image
	@echo "$(YELLOW)Building pfSense MCP Server v$(VERSION)...$(NC)"
	docker compose build --build-arg VERSION=$(VERSION)
	@echo "$(GREEN)Build complete$(NC)"

run: check-env ## Run with Docker Compose (HTTP mode)
	@echo "$(YELLOW)Starting pfSense MCP Server...$(NC)"
	docker compose up -d
	@echo "$(GREEN)Server started on port $${MCP_PORT:-3000}$(NC)"

run-local: check-env ## Run locally in stdio mode
	@echo "$(YELLOW)Starting in stdio mode...$(NC)"
	python3 -m src.main

run-http: check-env ## Run locally in HTTP mode
	@echo "$(YELLOW)Starting in HTTP mode...$(NC)"
	python3 -m src.main -t streamable-http

stop: ## Stop Docker Compose stack
	@echo "$(YELLOW)Stopping services...$(NC)"
	docker compose down
	@echo "$(GREEN)Services stopped$(NC)"

restart: stop run ## Restart Docker Compose stack

logs: ## View container logs
	docker compose logs -f pfsense-mcp

shell: ## Open shell in container
	docker compose exec pfsense-mcp /bin/bash

test: ## Run tests
	@echo "$(YELLOW)Running tests...$(NC)"
	python3 -m pytest tests/ -v

test-cov: ## Run tests with coverage
	@echo "$(YELLOW)Running tests with coverage...$(NC)"
	python3 -m pytest tests/ --cov=src --cov-report=term-missing

lint: ## Run linting
	@echo "$(YELLOW)Running linter...$(NC)"
	ruff check .

format: ## Format code
	@echo "$(YELLOW)Formatting code...$(NC)"
	ruff check --fix .

health-check: ## Check server health (HTTP mode only)
	@echo "$(YELLOW)Checking service health...$(NC)"
	@docker compose ps
	@echo ""
	@curl -sf http://localhost:$${MCP_PORT:-3000}/mcp && echo "$(GREEN)MCP endpoint healthy$(NC)" || echo "$(RED)MCP endpoint not responding$(NC)"

clean: ## Clean up containers and volumes
	@echo "$(RED)Warning: This will delete containers and logs!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker compose down -v; \
		rm -rf logs/; \
		echo "$(GREEN)Cleanup complete$(NC)"; \
	fi

push: ## Push image to registry
	@if [ -z "$(DOCKER_REGISTRY)" ]; then \
		echo "$(RED)Error: DOCKER_REGISTRY not set$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Pushing $(FULL_IMAGE_NAME):$(VERSION)...$(NC)"
	docker tag $(IMAGE_NAME):$(VERSION) $(FULL_IMAGE_NAME):$(VERSION)
	docker tag $(IMAGE_NAME):$(VERSION) $(FULL_IMAGE_NAME):latest
	docker push $(FULL_IMAGE_NAME):$(VERSION)
	docker push $(FULL_IMAGE_NAME):latest
	@echo "$(GREEN)Push complete$(NC)"

deploy: build push ## Build and push to registry

version: ## Show version
	@echo "pfSense MCP Server v$(VERSION)"
