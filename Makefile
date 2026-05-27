.PHONY: dev test lint build clean

dev:
	docker compose -f docker-compose.dev.yml up --build

test:
	cd backend && pytest tests/unit -v

test-integration:
	cd backend && INTEGRATION=1 pytest tests/integration -v

lint:
	cd backend && ruff check . && black --check .
	cd frontend && npm run lint

format:
	cd backend && ruff check --fix . && black .
	cd frontend && npm run lint -- --fix

build:
	docker compose build

clean:
	docker compose down -v
	find . -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
