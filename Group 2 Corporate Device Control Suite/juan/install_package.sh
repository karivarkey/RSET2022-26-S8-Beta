#!/bin/bash
# Install a package

# This script is run as root by client.js
# It receives the whitelisted package name as its first argument

package_name="$1"

echo "Starting installation for package ${package_name}"

# Update package lists with retry logic for transient network errors
echo "Updating package lists (will retry up to 3 times)..."
update_attempts=0
until apt-get update; do
    update_attempts=$((update_attempts + 1))
    if [ "$update_attempts" -ge 3 ]; then
        echo "ERROR: 'apt-get update' failed after 3 attempts" >&2
        exit 1
    fi
    echo "Retrying 'apt-get update' in 10 seconds..."
    sleep 10
done

# Install the package non-interactively (-y)
echo "Installing..."
if ! apt-get install -y "$package_name"; then
    echo "ERROR: Failed to install package '$package_name'" >&2
    exit 1
fi

echo "Installation for package '${package_name}' finished successfully"
