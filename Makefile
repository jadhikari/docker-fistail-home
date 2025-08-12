.PHONY: help build dev prod up down logs clean migrate collectstatic shell backup restore ssl-setup ssl-renew

# Default target
help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Setup commands
# Note: Environment files (.env.dev and .env.prod) should be created manually

# Development commands
dev: ## Start development environment
	docker compose -f docker-compose.dev.yml up --build

dev-detach: ## Start development environment in background
	docker compose -f docker-compose.dev.yml up --build -d

dev-logs: ## Show development logs
	docker compose -f docker-compose.dev.yml logs -f

# Production commands
prod: ## Start production environment
	docker compose -f docker-compose.prod.yml up --build -d

prod-logs: ## Show production logs
	docker compose -f docker-compose.prod.yml logs -f

# Build commands
build-dev: ## Build development images
	docker compose -f docker-compose.dev.yml build

build-prod: ## Build production images
	docker compose -f docker-compose.prod.yml build

# Stop commands
down-dev: ## Stop development environment
	docker compose -f docker-compose.dev.yml down

down-prod: ## Stop production environment
	docker compose -f docker-compose.prod.yml down

# Database commands
migrate: ## Run database migrations
	docker compose -f docker-compose.prod.yml --profile migrate up migrate

migrate-dev: ## Run database migrations in development
	docker compose -f docker-compose.dev.yml exec backend python manage.py migrate

makemigrations: ## Create new migrations
	docker compose -f docker-compose.dev.yml exec backend python manage.py makemigrations

# Migration commands (SIMPLE)
migration-status: ## Check migration status
	docker compose -f docker-compose.dev.yml exec backend python manage.py showmigrations

migration-fake: ## Fake migrations (use when tables exist but migrations missing)
	docker compose -f docker-compose.dev.yml exec backend python manage.py migrate --fake

migration-fake-initial: ## Fake initial migrations
	docker compose -f docker-compose.dev.yml exec backend python manage.py migrate --fake-initial

# Django commands
collectstatic: ## Collect static files
	docker compose -f docker-compose.prod.yml exec backend python manage.py collectstatic --noinput

createsuperuser: ## Create Django superuser
	docker exec -it fishtail-backend-dev python manage.py createsuperuser

shell: ## Open Django shell
	docker compose -f docker-compose.dev.yml exec backend python manage.py shell

# Database backup and restore
backup: ## Create database backup
	docker compose -f docker-compose.prod.yml exec postgres pg_dump -U $$POSTGRES_USER $$POSTGRES_DB > backup_$(shell date +%Y%m%d_%H%M%S).sql

restore: ## Restore database from backup (usage: make restore BACKUP_FILE=backup_20240101_120000.sql)
	docker compose -f docker-compose.prod.yml exec -T postgres psql -U $$POSTGRES_USER $$POSTGRES_DB < $(BACKUP_FILE)

# SSL certificate management
ssl-setup: ## Setup SSL certificates
	docker compose -f docker-compose.prod.yml --profile ssl up certbot

ssl-renew: ## Renew SSL certificates
	docker compose -f docker-compose.prod.yml run --rm certbot renew

# Maintenance commands
clean: ## Remove all containers, images, and volumes
	docker system prune -a --volumes -f

clean-dev: ## Clean development environment
	docker compose -f docker-compose.dev.yml down -v --rmi all

clean-prod: ## Clean production environment
	docker compose -f docker-compose.prod.yml down -v --rmi all

# Health checks
health: ## Check service health
	docker compose -f docker-compose.prod.yml ps

health-dev: ## Check development service health
	docker compose -f docker-compose.dev.yml ps

# Logs
logs-backend: ## Show backend logs
	docker compose -f docker-compose.prod.yml logs -f backend

logs-nginx: ## Show nginx logs
	docker compose -f docker-compose.prod.yml logs -f nginx

logs-postgres: ## Show postgres logs
	docker compose -f docker-compose.prod.yml logs -f postgres

# Development utilities
test: ## Run tests
	docker compose -f docker-compose.dev.yml exec backend python manage.py test

lint: ## Run code linting
	docker compose -f docker-compose.dev.yml exec backend python -m flake8 .

format: ## Format code
	docker compose -f docker-compose.dev.yml exec backend python -m black .

# Monitoring
monitor: ## Show resource usage
	docker stats

# Quick commands
restart: ## Restart all services
	docker compose -f docker-compose.prod.yml restart

restart-dev: ## Restart development services
	docker compose -f docker-compose.dev.yml restart 