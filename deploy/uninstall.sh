#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# lnmp Network Monitoring Platform - Production Uninstaller
# Supports: Debian 12+, Ubuntu 22.04+
# Usage: sudo bash deploy/uninstall.sh [--dry-run] [--force]
# ============================================================

DRY_RUN=false
FORCE=false

for arg in "$@"; do
    case "$arg" in
        --dry-run)
            DRY_RUN=true
            echo "DRY RUN MODE: No changes will be made."
            ;;
        --force)
            FORCE=true
            ;;
    esac
done

CONFIG_DIR="/etc/netmon"
ENV_FILE="$CONFIG_DIR/netmon.env"
INSTALL_DIR="/opt/netmon"
LOG_DIR="/var/log/netmon"
BACKUP_DIR="/var/backups/netmon"
NGINX_CONF="/etc/nginx/sites-available/netmon"
NGINX_ENABLED="/etc/nginx/sites-enabled/netmon"
LOGROTATE_CONF="/etc/logrotate.d/netmon"
CERT_FILE="/etc/ssl/certs/netmon.crt"
KEY_FILE="/etc/ssl/private/netmon.key"

# ============================================================
print_header() {
    echo ""
    echo "========================================================"
    echo "  $1"
    echo "========================================================"
}

run() {
    local description="$1"
    shift
    if [ "$DRY_RUN" = true ]; then
        echo "[DRY RUN] $description"
        echo "          Command: $*"
    else
        echo "--> $description"
        "$@" || echo "Warning: Command failed: $*"
    fi
}

check_root() {
    if [ "$EUID" -ne 0 ] && [ "$DRY_RUN" = false ]; then
        echo "Error: This script must be run as root."
        echo "Usage: sudo bash deploy/uninstall.sh"
        exit 1
    fi
}

# ============================================================
print_header "Step 1: Checking root privileges"
check_root

# Ask for confirmation if not forced
if [ "$FORCE" = false ] && [ "$DRY_RUN" = false ]; then
    echo "WARNING: This will completely uninstall the Netmon platform."
    echo "This includes stopping services, removing configurations, removing SSL certificates,"
    echo "deleting all files in /opt/netmon, and dropping the PostgreSQL 'netmon' database!"
    echo ""
    read -p "Are you sure you want to proceed? [y/N]: " CONFIRM
    if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
        echo "Uninstallation cancelled."
        exit 0
    fi
fi

# ============================================================
print_header "Step 2: Stopping and disabling systemd services"

for service in netmon-engine netmon-api; do
    if systemctl is-active --quiet "$service" 2>/dev/null; then
        run "Stopping $service service" systemctl stop "$service"
    fi
    if systemctl is-enabled --quiet "$service" 2>/dev/null; then
        run "Disabling $service service" systemctl disable "$service"
    fi
    
    dst="/etc/systemd/system/${service}.service"
    if [ -f "$dst" ]; then
        run "Removing service unit file $dst" rm -f "$dst"
    fi
done

run "Reloading systemd daemon" systemctl daemon-reload

# ============================================================
print_header "Step 3: Cleaning Nginx configuration"

if [ -f "$NGINX_ENABLED" ]; then
    run "Removing Nginx enabled link" rm -f "$NGINX_ENABLED"
fi

if [ -f "$NGINX_CONF" ]; then
    run "Removing Nginx site configuration" rm -f "$NGINX_CONF"
fi

if [ "$DRY_RUN" = false ]; then
    if command -v nginx &>/dev/null && nginx -t >/dev/null 2>&1; then
        run "Reloading Nginx" systemctl reload nginx
    else
        echo "Warning: Nginx not active or configuration invalid, skipping reload."
    fi
else
    echo "[DRY RUN] Would reload Nginx"
fi

# ============================================================
print_header "Step 4: Cleaning self-signed SSL certificates"

for file in "$CERT_FILE" "$KEY_FILE"; do
    if [ -f "$file" ]; then
        run "Removing certificate file $file" rm -f "$file"
    fi
done

# ============================================================
print_header "Step 5: Cleaning logrotate configuration"

if [ -f "$LOGROTATE_CONF" ]; then
    run "Removing logrotate configuration" rm -f "$LOGROTATE_CONF"
fi

# ============================================================
print_header "Step 6: Dropping PostgreSQL database and role"

if [ "$DRY_RUN" = false ]; then
    if command -v psql &>/dev/null; then
        echo "--> Terminating active connections to 'netmon' database"
        sudo -u postgres psql -c \
            "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = 'netmon' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true
        
        echo "--> Dropping database 'netmon'"
        sudo -u postgres psql -c "DROP DATABASE IF EXISTS netmon;" || true
        
        echo "--> Dropping database role 'netmon_user'"
        sudo -u postgres psql -c "DROP ROLE IF EXISTS netmon_user;" || true
    else
        echo "PostgreSQL client not found. Database drop skipped."
    fi
else
    echo "[DRY RUN] Would terminate connections, drop database 'netmon', and drop role 'netmon_user'"
fi

# ============================================================
print_header "Step 7: Removing system user and group"

if id "netmon" &>/dev/null; then
    run "Deleting system user 'netmon'" userdel -r netmon
else
    echo "System user 'netmon' does not exist."
fi

# ============================================================
print_header "Step 8: Cleaning up directories"

for dir in "$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR" "$BACKUP_DIR"; do
    if [ -d "$dir" ]; then
        run "Recursively deleting directory $dir" rm -rf "$dir"
    else
        echo "Directory $dir does not exist."
    fi
done

# ============================================================
print_header "Uninstallation Complete"

if [ "$DRY_RUN" = true ]; then
    echo "DRY RUN complete. No changes were made."
else
    echo "The Netmon platform has been successfully uninstalled."
fi
echo "========================================================"
