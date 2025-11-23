# Use PHP 8.1 CLI as base
FROM php:8.1-cli

# Install Python3, venv, git, curl
RUN apt-get update && apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Create a virtual environment
RUN python3 -m venv /app/venv

# Activate venv and install Python dependencies
RUN /app/venv/bin/pip install --no-cache-dir -r requirements.txt

# Expose ports
EXPOSE 80 8000

# Set PATH to use venv pip/python
ENV PATH="/app/venv/bin:$PATH"

# Run Python app
CMD ["python3", "app.py"]
