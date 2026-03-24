#!/bin/bash
# List user-installed Linux packages (excluding dependencies & default packages)

# Get cur directory where script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Specify file of default system packages to exclude
WHITELIST_FILE="$SCRIPT_DIR/default_packages.txt"

# List manually installed packages
output=$(apt-mark showmanual)

# Filter libraries
filtered=$(echo "$output" \
    | grep -Ev '^(lib|gir1\.|fonts-|python|gstreamer|linux-|xserver|mesa-|gnome-|kde-|qt[0-9]?|ubuntu|language-|task-)' \
    | grep -Fxv -f "$WHITELIST_FILE" \
    | sort)

echo "$filtered"