#!/bin/bash

# Default Nginx configuration directory
NGINX_CONF_DIR="/etc/nginx/conf.d"
# Default frontend directory
FRONTEND_DIR="/fronted/dist"

# Check if script is run as root
if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root. Please use sudo." >&2
  exit 1
fi

# Check if Nginx is installed
if ! command -v nginx &> /dev/null; then
    echo "Nginx could not be found. Please install Nginx first."
    exit 1
fi

# Create a backup of the existing default configuration if it exists
if [ -f "${NGINX_CONF_DIR}/default.conf" ]; then
    echo "Backing up existing default.conf to default.conf.backup..."
    mv "${NGINX_CONF_DIR}/default.conf" "${NGINX_CONF_DIR}/default.conf.backup"
fi

# Copy the new Nginx configuration
echo "Copying nginx.conf to ${NGINX_CONF_DIR}/app.conf..."
cp ./nginx.conf "${NGINX_CONF_DIR}/app.conf"

# Check Nginx configuration syntax
echo "Testing Nginx configuration..."
if nginx -t; then
    echo "Nginx configuration test successful."
else
    echo "Nginx configuration test failed. Please check nginx.conf."
    # Restore backup if it exists
    if [ -f "${NGINX_CONF_DIR}/default.conf.backup" ]; then
        echo "Restoring backup..."
        mv "${NGINX_CONF_DIR}/default.conf.backup" "${NGINX_CONF_DIR}/default.conf"
    fi
    exit 1
fi

# Reload Nginx
echo "Reloading Nginx..."
if systemctl reload nginx; then
    echo "Nginx reloaded successfully."
else
    echo "Failed to reload Nginx. Please check Nginx status."
    # Restore backup if it exists
    if [ -f "${NGINX_CONF_DIR}/default.conf.backup" ]; then
        echo "Restoring backup..."
        mv "${NGINX_CONF_DIR}/default.conf.backup" "${NGINX_CONF_DIR}/default.conf"
    fi
    exit 1
fi

echo "Nginx setup complete. Your application should be accessible."
echo "Frontend is served from ${FRONTEND_DIR}"
echo "Backend API is proxied from /api/ to http://localhost:8000" 