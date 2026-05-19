.PHONY: init up down test lint seed shell logs clean reset backup build

APP_NAME = agentos
DOCKER_COMPOSE = docker compose

init: build seed
	@echo "✓ AgentOS initialized. Run 'make up' to start."

build:
	$(DOCKER_COMPOSE) build
	@echo "✓ Images built."

up:
	$(DOCKER_COMPOSE) up -d
	@echo "✓ AgentOS is running."
	@echo "  API:     http://localhost:8000"
	@echo "  Docs:    http://localhost:8000/docs"
	@echo "  Dashboard: http://localhost:3000"
	@echo "  MailHog: http://localhost:8025"
	@echo "  Strapi:  http://localhost:1337"

down:
	$(DOCKER_COMPOSE) down
	@echo "✓ AgentOS stopped."

logs:
	$(DOCKER_COMPOSE) logs -f

shell:
	$(DOCKER_COMPOSE) exec app bash

test:
	$(DOCKER_COMPOSE) exec app python -m pytest $(ARGS)

lint:
	$(DOCKER_COMPOSE) exec app ruff check app/
	$(DOCKER_COMPOSE) exec app mypy app/

seed:
	@mkdir -p docker/postgres
	@chmod +x docker/postgres/init.sql 2>/dev/null || true
	@echo "✓ Seed data configured."

clean:
	$(DOCKER_COMPOSE) down -v
	docker system prune -f --volumes
	@echo "✓ Cleaned volumes and stopped containers."

reset: down clean init up
	@echo "✓ AgentOS fully reset."

backup:
	@mkdir -p backups
	$(DOCKER_COMPOSE) exec -T postgres pg_dump -U agentos agentos > backups/agentos_$$(date +%Y%m%d_%H%M%S).sql
	@echo "✓ Database backup saved to backups/"

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

install:
	pip install -r requirements.txt
	@echo "✓ Dependencies installed."
