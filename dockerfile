# Use PHP 8.1 CLI as base
FROM php:8.1-cli

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    git \
    curl \
    wget \
    unzip \
    libzip-dev \
    libpng-dev \
    libjpeg-dev \
    libfreetype6-dev \
    libonig-dev \
    libxml2-dev \
    libmagickwand-dev \
    && rm -rf /var/lib/apt/lists/*

# Install PHP extensions required by PipraPay
RUN docker-php-ext-install \
    mysqli \
    pdo \
    pdo_mysql \
    gd \
    fileinfo \
    mbstring \
    zip

# Install Imagick via PECL
RUN pecl install imagick && \
    docker-php-ext-enable imagick

# Install IonCube Loader for PHP 8.1
RUN cd /tmp && \
    curl -fsSL -o ioncube.tar.gz https://downloads.ioncube.com/loader_downloads/ioncube_loaders_lin_x86-64.tar.gz && \
    tar -xzf ioncube.tar.gz && \
    PHP_EXT_DIR=$(php-config --extension-dir) && \
    cp ioncube/ioncube_loader_lin_8.1.so ${PHP_EXT_DIR}/ioncube_loader_lin_8.1.so && \
    echo "zend_extension=ioncube_loader_lin_8.1.so" > /usr/local/etc/php/conf.d/00-ioncube.ini && \
    rm -rf /tmp/ioncube.tar.gz /tmp/ioncube

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Create Python virtual environment
RUN python3 -m venv /app/venv

# Install Python dependencies
RUN /app/venv/bin/pip install --no-cache-dir -r requirements.txt

# Set proper file permissions for PipraPay folders
RUN if [ -d "project" ]; then \
    chmod -R 755 project && \
    if [ -d "project/invoice" ]; then chmod -R 777 project/invoice; fi && \
    if [ -d "project/payment" ]; then chmod -R 777 project/payment; fi && \
    if [ -d "project/admin" ]; then chmod -R 777 project/admin; fi && \
    if [ -d "project/pp-include" ]; then chmod -R 777 project/pp-include; fi; \
    fi

# Expose ports
EXPOSE 80 8000

# Set PATH to use venv
ENV PATH="/app/venv/bin:$PATH"

# Run Python app
CMD ["python3", "app.py"]
