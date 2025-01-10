# Use an official Python image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install required system packages
RUN apt-get update && apt-get install -y \
    python3-venv \
    zip \
    && rm -rf /var/lib/apt/lists/*

# Copy project files into the container
COPY . .

# Set executable permissions for the deployment script
RUN chmod +x lambda_deploy.sh

# Default command to run the deployment script
CMD ["./lambda_deploy.sh"]

