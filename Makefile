.PHONY: help install clean test lint format version info

SOURCE_DIR := labellerr
PYTHON := python3
PIP := pip3

help:
	@echo "Labellerr SDK - Simple Development Commands"
	@echo "=========================================="
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*?##/ { printf "  %-15s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage .pytest_cache/ .mypy_cache/

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	flake8 .

format:
	black .

build: ## Build package
	$(PYTHON) -m build

version: 
	@grep '^version = ' pyproject.toml | cut -d'"' -f2 | sed 's/^/Current version: /' || echo "Version not found"

info: 
	@echo "Python: $(shell $(PYTHON) --version)"
	@echo "Working directory: $(shell pwd)"
	@echo "Git branch: $(shell git branch --show-current 2>/dev/null || echo 'Not a git repository')"
	@make version