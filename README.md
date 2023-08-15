# troposphere-infrastructure
Repo to demonstrate Troposphere repo layout and scalability. Mono repo intended for a single AWS account.

# Setup
1. Install Docker
2. Clone this repo
3. Set secret credentials in repo settings >> "Secrets and variables" >> Actions:
![img.png](images/img.png)
![img_1.png](images/img_1.png)
4. Add your templates in src/stack-name/template.py
5. Run `make all` to build your templates

# Usage

## Template generation
1. Add template files: src/stack-name/template.py
2. Execute, build and lint your templates `make all`

Optionally, you can execute a number of individual commands using make:

`make all` - Runs black to lint formatting issues, cfn-lint to lint CloudFormation templates, and build your templates after building the Docker image
`make docker` - Build the container image for your project dependencies used in subsequent commands
`make black-fix` - Runs black to fix formatting issues, this is not part of `make all`
`make black-lint` - Runs black to lint formatting issues
`make cfn-lint` - Runs cfn-lint to lint CloudFormation templates.
`make cfn-templates` - Builds your CloudFormation templates
``