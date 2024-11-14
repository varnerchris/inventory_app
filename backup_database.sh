#!/bin/bash

DB_PATH="${DB_PATH:-./inventory.db}"  # Path to the database file; defaults to 'inventory.db' in current directory
BACKUP_DIR="${BACKUP_DIR:-/mnt/external_drive/backups}"  # Path to backup directory; defaults to an external drive path

# Create the backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Define the backup file name with timestamp
BACKUP_FILE="$BACKUP_DIR/inventory_backup_$(date +'%Y%m%d_%H%M%S').db"

# Perform the backup
cp "$DB_PATH" "$BACKUP_FILE"

# Print a confirmation message
echo "Backup created at $BACKUP_FILE"
