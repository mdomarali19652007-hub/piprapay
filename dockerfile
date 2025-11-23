# Use an official PHP + Python base
FROM php:8.1-cli

# Install Python 3 and pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Expose ports
# 80 for Python (Render will use $PORT), 8000 for PHP internal
EXPOSE 80 8000

# Run your Python app
CMD ["python3", "app.py"]
