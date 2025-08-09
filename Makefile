# Makefile for oaat-operator testing
.PHONY: help test-ci-local test-unit test-integration lint clean build-docker

# Default target
help:
	@echo "🛠️  oaat-operator Testing Commands"
	@echo ""
	@echo "Local Development:"
	@echo "  make test-unit          Run unit tests locally (fast)"
	@echo "  make test-unit-coverage Run unit tests locally with coverage (fast)"
	@echo "  make test-integration   Run integration tests locally (requires k3d)"
	@echo "  make lint               Run linting checks locally"
	@echo ""
	@echo "CI Simulation:"
	@echo "  make test-ci-local     🐳 Run all tests in CI-like Docker environment"
	@echo "  make test-docker-unit  🐳 Run only unit tests in Docker"
	@echo "  make test-docker-lint  🐳 Run only linting in Docker"
	@echo ""
	@echo "Docker Management:"
	@echo "  make build-docker      🐳 Build/rebuild Docker test image"
	@echo "  make debug-docker      🐳 Interactive shell in test environment"
	@echo "  make clean-docker      🐳 Clean up Docker test environment"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean             Clean up coverage and cache files"

# Local testing (requires local environment setup)
test-unit:
	@if [ -f .venv/bin/activate ]; then \
		. .venv/bin/activate && python3 tests/unit/run_tests_with_mocking.py tests/unit/ -v; \
	else \
		python3 tests/unit/run_tests_with_mocking.py tests/unit/ -v; \
	fi

# Local testing with coverage (requires local environment setup)
test-unit-coverage:
	@if [ -f .venv/bin/activate ]; then \
		. .venv/bin/activate && python3 tests/unit/run_tests_with_mocking.py tests/unit/ -v --cov=oaatoperator --cov-report=term --cov-report=xml:coverage-reports/cov.xml; \
	else \
		python3 tests/unit/run_tests_with_mocking.py tests/unit/ -v --cov=oaatoperator --cov-report=term --cov-report=xml:coverage-reports/cov.xml; \
	fi

test-integration:
	@. .venv/bin/activate && tests/integration/setup.sh
	. .venv/bin/activate && python3 -m pytest tests/integration/ -v

lint:
	. .venv/bin/activate && flake8 . --count --exclude .venv --select=E9,F63,F7,F82 --show-source --statistics
	. .venv/bin/activate && flake8 . --count --exclude .venv --exit-zero --max-complexity=10 --max-line-length=127 --statistics

# CI simulation with Docker (no local env required)
test-ci-local:
	@echo "🐳 Running CI simulation locally..."
	./scripts/test-ci-local.sh

test-docker-unit:
	docker-compose -f docker-compose.test.yml run --rm unit-tests

test-docker-lint:
	docker-compose -f docker-compose.test.yml run --rm lint-check

test-docker-coverage:
	docker-compose -f docker-compose.test.yml run --rm unit-tests-coverage

# Docker management
build-docker:
	@echo "🐳 Building Docker test image..."
	docker-compose -f docker-compose.test.yml build --no-cache debug

# Debug and utilities
debug-docker:
	@echo "🐳 Starting interactive shell in CI-like environment..."
	docker-compose -f docker-compose.test.yml run --rm debug

clean-docker:
	@echo "🐳 Cleaning up Docker test environment..."
	docker-compose -f docker-compose.test.yml down --rmi local
	docker system prune -f

clean:
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf coverage-reports/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
