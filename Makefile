# Makefile for Silvertine trading system development

.PHONY: help install install-dev test test-unit test-integration test-cov lint format typecheck clean run setup pre-commit docker

# Default target
help:
	@echo "Silvertine Trading System - Development Commands"
	@echo ""
	@echo "Setup and Installation:"
	@echo "  install          Install production dependencies"
	@echo "  install-dev      Install development dependencies"
	@echo "  setup           Full development environment setup"
	@echo "  pre-commit      Install and setup pre-commit hooks"
	@echo ""
	@echo "Code Quality:"
	@echo "  format          Format code with black and isort"
	@echo "  lint            Run linting with ruff"
	@echo "  typecheck       Run type checking with mypy"
	@echo "  clean           Clean up cache and build artifacts"
	@echo ""
	@echo "Testing:"
	@echo "  test            Run all tests"
	@echo "  test-unit       Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-cov        Run tests with coverage report"
	@echo ""
	@echo "Application:"
	@echo "  run             Start the trading system"
	@echo "  docker          Build and run Docker container"

# Installation targets
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

setup: install-dev pre-commit
	@echo "Development environment setup complete!"

pre-commit:
	pre-commit install
	pre-commit install --hook-type commit-msg

# Code quality targets
format:
	black src/ tests/
	isort src/ tests/

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

typecheck:
	mypy src/

# Testing targets
test:
	pytest

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-cov:
	pytest --cov=src --cov-report=html --cov-report=term-missing

# Application targets
run:
	python -m src.main

# Utility targets
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/

# Docker targets
docker:
	docker build -t silvertine:latest .
	@echo "Run with: docker run -it --rm silvertine:latest"

# Development workflow
dev-check: format lint typecheck test-unit
	@echo "Development checks passed!"

# CI/CD simulation
ci: install-dev format lint typecheck test
	@echo "CI pipeline simulation complete!"