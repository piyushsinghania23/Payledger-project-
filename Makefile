# Makefile for Playto Payout Engine

.PHONY: help setup install migrate seed test test-concurrency test-idempotency \
        run-backend run-celery run-frontend run-all clean docker-up docker-down

help:
	@echo "Playto Payout Engine - Available Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make setup              - Set up everything (backend, frontend, database)"
	@echo "  make install-backend    - Install Python dependencies"
	@echo "  make install-frontend   - Install Node dependencies"
	@echo ""
	@echo "Database:"
	@echo "  make migrate            - Run Django migrations"
	@echo "  make seed               - Seed database with merchants"
	@echo ""
	@echo "Testing:"
	@echo "  make test               - Run all tests"
	@echo "  make test-concurrency   - Run concurrency tests only"
	@echo "  make test-idempotency   - Run idempotency tests only"
	@echo ""
	@echo "Running:"
	@echo "  make run-backend        - Run Django development server"
	@echo "  make run-celery         - Run Celery worker"
	@echo "  make run-frontend       - Run React development server"
	@echo "  make run-all            - Run all services together"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up          - Start all services with docker-compose"
	@echo "  make docker-down        - Stop all services"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean              - Remove pycache, node_modules, etc."

setup: install-backend install-frontend migrate seed
	@echo "✓ Setup complete!"

install-backend:
	cd backend && pip install -r requirements.txt

install-frontend:
	cd frontend && npm install

migrate:
	cd backend && python manage.py migrate

seed:
	cd backend && python manage.py seed_merchants

test:
	cd backend && pytest payto/payout/tests.py -v

test-concurrency:
	cd backend && pytest payto/payout/tests.py::TestConcurrentPayouts -v

test-idempotency:
	cd backend && pytest payto/payout/tests.py::TestIdempotency -v

run-backend:
	cd backend && python manage.py runserver 0.0.0.0:8000

run-celery:
	cd backend && celery -A payto worker -l info

run-frontend:
	cd frontend && npm start

run-all:
	@echo "Starting all services..."
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"
	@echo "API Docs: http://localhost:8000/api/docs/"
	@echo ""
	@tmux new-session -d -s payto-backend -c backend "python manage.py runserver 0.0.0.0:8000"
	@tmux new-window -t payto-backend -n celery -c backend "celery -A payto worker -l info"
	@tmux new-window -t payto-backend -n frontend -c frontend "npm start"
	@echo "✓ All services started in tmux session 'payto-backend'"
	@echo "View logs: tmux attach-session -t payto-backend"

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf frontend/node_modules
	rm -rf frontend/build
	rm -rf backend/.coverage
	rm -rf backend/htmlcov
	@echo "✓ Cleaned up cache files"
