#!/bin/bash
# Delete packages

# Check for --dry-run as the last argument
# For dev purposes
DRY_RUN=false

if [[ "${!#}" == "--dry-run" ]]; then
    DRY_RUN=true
    # Remove --dry-run from provided list of packages
    set -- "${@:1:$(($#-1))}"
fi

PACKAGES=("$@")

echo "Packages to delete:"
for pkg in "${PACKAGES[@]}"; do
    echo " - $pkg"
done

if $DRY_RUN; then
    echo "DRY RUN: No packages removed"
else
    echo "Deleting packages..."
    apt-get remove --purge -y "${PACKAGES[@]}"
    apt-get autoremove -y
    echo "Deletion completed"
fi
