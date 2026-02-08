.PHONY: help docs-serve docs-build docs-deploy docs-install clean test lint format

help:  ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Documentation targets
docs-install:  ## Install documentation dependencies
	poetry install --with docs

docs-serve:  ## Serve documentation locally with live reload
	poetry run python -m mkdocs serve

docs-build:  ## Build static documentation site
	poetry run python -m mkdocs build

docs-deploy:  ## Deploy documentation to GitHub Pages
	poetry run python -m mkdocs gh-deploy

# Development targets
install:  ## Install all dependencies
	poetry install

test:  ## Run tests
	poetry run pytest

lint:  ## Run linters
	poetry run ruff check project_subway tests

format:  ## Format code
	poetry run black project_subway tests

clean:  ## Clean build artifacts
	rm -rf site/
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
