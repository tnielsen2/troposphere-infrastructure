# Define the default target
.DEFAULT_GOAL := help

.PHONY: all
all: black-fmt cfn-templates cfn-lint

.PHONY: black-fmt
black-fmt:
	@echo "Running black linting..."
	@docker build -t troposphere-infrastructure:local .
	@docker run -it -v $(pwd):/app troposphere-infrastructure:local black --check --diff .

.PHONY: cfn-templates
cfn-templates:
	@echo "Creating CloudFormation templates..."
	@docker build -t troposphere-infrastructure:local .
	@docker run -it -v $(pwd):/app troposphere-infrastructure:local

.PHONY: cfn-lint
cfn-lint:
	@echo "Running CloudFormation linting..."
	@docker build -t troposphere-infrastructure:local .
	@docker run -it -v $(pwd):/app troposphere-infrastructure:local cfn-lint cfn/**/*.json -a tests/cfn-lint/rules

.PHONY: lint
lint: black-fmt cfn-lint

.PHONY: help
help:
	@echo "Usage:"
	@echo "  make all   Create and lint CloudFormation templates"
	@echo "  make black-fmt   Run black linting"
	@echo "  make cfn-templates Create CloudFormation templates"
	@echo "  make cfn-lint    Run CloudFormation linting"
	@echo "  make help        Show this help message"
