# Define the default target
.DEFAULT_GOAL := help

.PHONY: all
all: docker lint cfn-templates

.PHONY: fix
fix:
	@echo "Running black formatting..."
	@docker run -it -v $(shell pwd):/troposphere-infrastructure -w /troposphere-infrastructure troposphere-infrastructure:local black .

.PHONY: black-lint
black-lint:
	@echo "Running black linting..."
	@docker run -it -v $(shell pwd):/troposphere-infrastructure -w /troposphere-infrastructure troposphere-infrastructure:local black --check --diff .

.PHONY: cfn-templates
cfn-templates:
	@echo "Creating CloudFormation templates..."
	@docker run -it -v $(shell pwd):/troposphere-infrastructure -w /troposphere-infrastructure troposphere-infrastructure:local python __main__.py

.PHONY: cfn-lint
cfn-lint:
	@echo "Running CloudFormation linting..."
	@docker run -it -v $(shell pwd):/troposphere-infrastructure -w /troposphere-infrastructure troposphere-infrastructure:local cfn-lint "/troposphere-infrastructure/cfn/**/*.json" -a "/troposphere-infrastructure/tests/cfn-lint/rules"

.PHONY: docker
docker:
	@echo "Building Docker image..."
	@docker build -t troposphere-infrastructure:local .

.PHONY: lint
lint: black-lint cfn-lint pytest

.PHONY: pytest
pytest:
	@echo "Running Pytest..."
	@docker run -it -v $(shell pwd):/troposphere-infrastructure -w /troposphere-infrastructure troposphere-infrastructure:local pytest tests/

.PHONY: help
help:
	@echo "Usage:"
	@echo "  make all             Create and lint CloudFormation templates"
	@echo "  make black-lint      Run black linting"
	@echo "  make cfn-templates   Create CloudFormation templates"
	@echo "  make cfn-lint        Run CloudFormation linting"
	@echo "  make help            Show this help message"
	@echo "  make lint            Run all linting and tests"
	@echo "  make pytest          Run pytest"
