#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# lnmp Network Monitoring Platform - Admin Password Resetter
# Usage: sudo bash deploy/reset-admin-password.sh [new_password]
# ============================================================

if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root."
    exit 1
fi

ENV_FILE="/etc/netmon/netmon.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: Netmon configuration file not found at $ENV_FILE."
    echo "Please ensure the platform is installed before resetting the password."
    exit 1
fi

DB_PASS=$(grep NETMON_DB_PASSWORD "$ENV_FILE" | cut -d'=' -f2-)
SECRET_KEY=$(grep NETMON_SECRET_KEY "$ENV_FILE" | cut -d'=' -f2-)

NEW_PASS="${1:-}"
if [ -z "$NEW_PASS" ]; then
    read -s -p "Enter new admin password (leave blank to auto-generate): " NEW_PASS
    echo ""
    if [ -z "$NEW_PASS" ]; then
        NEW_PASS="admin"
        echo "Defaulting new admin password to: $NEW_PASS"
    fi
fi

sudo -u netmon \
    NETMON_DB_PASSWORD="$DB_PASS" \
    NETMON_SECRET_KEY="$SECRET_KEY" \
    DEFAULT_ADMIN_PASSWORD="$NEW_PASS" \
    FORCE_RESET_ADMIN="true" \
    PYTHONPATH="/opt/netmon/noop/backend" \
    /opt/netmon/venv/bin/python3 -m app.seed_admin

echo ""
echo "--------------------------------------------------------"
echo "  Updated Admin Credentials"
echo "  Username: admin"
echo "  Password: $NEW_PASS"
echo "--------------------------------------------------------"
