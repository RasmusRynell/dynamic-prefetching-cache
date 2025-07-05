# Makefile for dynamic-prefetching-cache

.PHONY: install test test-unit test-integration test-cov clean lint

# Install development dependencies
install:
	pip install -e ".[dev]"

# Run all tests
test:
	pytest

# Run unit tests only
test-unit:
	pytest -m unit

# Run integration tests only
test-integration:
	pytest -m integration

# Run tests with coverage
test-cov:
	pytest --cov=src/dynamic_prefetching_cache --cov-report=html --cov-report=term-missing

# Run tests excluding slow ones
test-fast:
	pytest -m "not slow"

# Run type checking
lint:
	mypy src/

# Clean up generated files
clean:
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -delete

# Show help
help:
	@echo "Available commands:"
	@echo "  install        - Install development dependencies"
	@echo "  test           - Run all tests"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-cov       - Run tests with coverage report"
	@echo "  test-fast      - Run tests excluding slow ones"
	@echo "  lint           - Run type checking"
	@echo "  clean          - Clean up generated files" 