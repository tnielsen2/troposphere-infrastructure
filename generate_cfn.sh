#!/bin/bash

# Build the Docker image (if not already built)
docker build -t troposphere-infrastructure:local .

# Get the absolute path of the current working directory
CURRENT_DIR=$(pwd)

# Run the Docker container, mounting the current directory into /app
docker run -it --rm -v "$CURRENT_DIR:/app" troposphere-infrastructure:local
