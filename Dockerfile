# Use an official Python runtime as the base image
FROM python:3.11-slim

# Set the working directory to /app
WORKDIR /troposphere_infrastructure

# Copy the current directory contents into the container at /app
COPY requirements.txt /troposphere_infrastructure

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Set empty CMD file for easy Makefile execution
CMD []
