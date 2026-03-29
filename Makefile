# Makefile for Calculus Animator
# Provides convenient shortcuts for common development tasks

.PHONY: help install install-dev test test-quick test-full test-fuzz test-e2e lint format type-check quality clean build run run-ai

# Default target
help:
	@echo "Calculus Animator - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install production dependencies"
	@echo "  make install-dev    Install development dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test           Run quick test suite (unit + integration)"
	@echo "  make test-quick     Run only unit tests"
	@echo "  make test-full      Run full test suite including snapshots"
	@echo "  make test-fuzz      Run property-based fuzz tests (slow)"
	@echo "  make test-e2e       Run end-to-end tests"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           Run ruff linter"
	@echo "  make format         Format code with ruff"
	@echo "  make type-check     Run mypy type checker"
	@echo "  make quality        Run full quality pipeline"
	@echo ""
	@echo "Development:"
	@echo "  make run            Run the application"
	@echo "  make run-ai         Run with AI tutor enabled"
	@echo "  make build          Build packaged release"
	@echo "  make clean          Clean build artifacts"
	@echo ""

# Installation
install:
	pip install -r requirements.txt

install-dev: install
	pip install -r requirements-dev.txt

# Testing
test:
	python scripts/run_tests.py

test-quick:
	python scripts/run_tests.py --quick

test-full:
	python scripts/run_tests.py --full

test-fuzz:
	python scripts/run_tests.py --fuzz

test-e2e:
	python scripts/run_tests.py --e2e

# Code Quality
lint:
	ruff check .

lint-fix:
	ruff check . --fix

format:
	ruff format .

type-check:
	mypy api core

quality:
	python scripts/run_quality.py

# Development
run:
	python run.py

# Build
build:
	python scripts/build_release.py

clean:
	rm -rf build/ dist/ __pycache__ .pytest_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Release Helpers
release-check:
	python scripts/run_release_checklist.py

# Documentation
docs-serve:
	@echo "Documentation is in README.md and other markdown files"
	@echo "Open README.md in your preferred markdown viewer"

# All checks before PR
pr-ready: lint type-check test
	@echo "All checks passed! Ready for PR."
