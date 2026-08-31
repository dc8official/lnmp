#!/usr/bin/env bash
# ==============================================================================
# LNMP Network Monitoring Platform v3.0.0 - Automated Upgrade Utility
# ==============================================================================

set -euo pipefail

# Color Palette for Terminal Output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Require Root / Administrative Privileges (bypassed in dry-run mode)
if [[ ${EUID} -ne 0 && "${1:-}" != "--dry-run" ]]; then
    echo -e "${RED}[ERROR] This script must be executed with root privileges (e.g., sudo ./upgrade.sh).${NC}" >&2
    exit 1
fi

echo -e "${BLUE}========================================================================${NC}"
echo -e "${BLUE}    LNMP Network Monitoring Platform v3.0.0 - Upgrade Utility           ${NC}"
echo -e "${BLUE}========================================================================${NC}"

# Resolve Script and Project Root Directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 2. Read Configuration Values
ENV_FILE="/etc/netmon/netmon.env"
if [[ -f "${ENV_FILE}" ]]; then
    echo -e "${GREEN}[INFO] Loading environment configuration from ${ENV_FILE}${NC}"
    # shellcheck disable=SC1090
    set -a
    source "${ENV_FILE}"
    set +a
elif [[ -f "${PROJECT_ROOT}/backend/.env" ]]; then
    echo -e "${YELLOW}[WARN] /etc/netmon/netmon.env not found. Loading local backend/.env${NC}"
    # shellcheck disable=SC1090
    set -a
    source "${PROJECT_ROOT}/backend/.env"
    set +a
fi

DB_NAME="${NETMON_DB_NAME:-${POSTGRES_DB:-netmon}}"
DB_USER="${NETMON_DB_USER:-${POSTGRES_USER:-netmon_user}}"
DB_PASS="${NETMON_DB_PASSWORD:-${POSTGRES_PASSWORD:-netmon_secure_password}}"
DB_HOST="${NETMON_DB_HOST:-${POSTGRES_HOST:-127.0.0.1}}"
DB_PORT="${NETMON_DB_PORT:-${POSTGRES_PORT:-5432}}"

# Handle Dry-Run Mode Option
DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=1
    echo -e "${YELLOW}[DRY-RUN MODE] Simulating upgrade operations without making mutations.${NC}"
fi

# 3. Pre-Upgrade Database Backup
BACKUP_DIR="/var/backups/netmon"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/netmon_backup_${TIMESTAMP}.sql"

echo -e "\n${BLUE}--- Step 1/7: Executing Pre-Upgrade Database Backup ---${NC}"
if [[ ${DRY_RUN} -eq 0 ]]; then
    if ! command -v pg_dump &> /dev/null; then
        echo -e "${RED}[ERROR] pg_dump command not found. Please install postgresql-client.${NC}" >&2
        exit 1
    fi

    mkdir -p "${BACKUP_DIR}"
    chmod 750 "${BACKUP_DIR}"
    echo -e "${GREEN}[INFO] Creating timestamped database dump at ${BACKUP_FILE}...${NC}"
    
    if PGPASSWORD="${DB_PASS}" pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -F p -f "${BACKUP_FILE}"; then
        chmod 640 "${BACKUP_FILE}"
        echo -e "${GREEN}[SUCCESS] Pre-upgrade backup successfully saved to ${BACKUP_FILE}${NC}"
    else
        echo -e "${RED}[ERROR] Database backup failed. Aborting upgrade to preserve data safety.${NC}" >&2
        exit 1
    fi
else
    echo -e "[DRY-RUN] Would generate SQL dump to ${BACKUP_FILE}"
fi

# 4. Smart Config Migration (In-Place Upgrade)
CONFIG_FILE="/etc/netmon/config.toml"
echo -e "\n${BLUE}--- Step 2/7: Migrating System Configuration Defaults ---${NC}"
if [[ ${DRY_RUN} -eq 0 && -f "${CONFIG_FILE}" ]]; then
    echo -e "${GREEN}[INFO] Verifying configuration settings in ${CONFIG_FILE}...${NC}"
    
    # Update ping timing budget to 5 pings @ 8.0s for v3.0.0
    if grep -q "ping_count = 10" "${CONFIG_FILE}"; then
        sed -i 's/ping_count = 10/ping_count = 5/' "${CONFIG_FILE}"
        echo -e "${GREEN}[INFO] Updated ping_count to 5 probes.${NC}"
    fi
    if grep -q "ping_interval_seconds = 6" "${CONFIG_FILE}"; then
        sed -i 's/ping_interval_seconds = 6/ping_interval_seconds = 8/' "${CONFIG_FILE}"
        echo -e "${GREEN}[INFO] Updated ping_interval_seconds to 8s.${NC}"
    fi

    # Update session_timeout_minutes to 120 if currently 30
    if grep -q "session_timeout_minutes = 30" "${CONFIG_FILE}"; then
        sed -i 's/session_timeout_minutes = 30/session_timeout_minutes = 120/' "${CONFIG_FILE}"
        echo -e "${GREEN}[INFO] Updated session_timeout_minutes to 120 (2 hours).${NC}"
    fi

    # Add max_active_sessions_per_user if missing
    if ! grep -q "max_active_sessions_per_user" "${CONFIG_FILE}"; then
        sed -i '/\[security\]/a max_active_sessions_per_user = 2' "${CONFIG_FILE}"
        echo -e "${GREEN}[INFO] Added max_active_sessions_per_user = 2 to [security].${NC}"
    fi

    # Add [redis] section if missing
    if ! grep -q "\[redis\]" "${CONFIG_FILE}"; then
        cat << 'EOF' >> "${CONFIG_FILE}"

[redis]
host = "127.0.0.1"
port = 6379
db = 0
enabled = true
performance_mode = false
EOF
        echo -e "${GREEN}[INFO] Appended [redis] storage driver section to ${CONFIG_FILE}.${NC}"
    fi
fi

# 5. Service Pause
echo -e "\n${BLUE}--- Step 3/7: Gracefully Pausing Platform Background Daemons ---${NC}"
if [[ ${DRY_RUN} -eq 0 ]]; then
    if systemctl is-active --quiet netmon-engine || systemctl is-active --quiet netmon-api; then
        echo -e "${GREEN}[INFO] Stopping netmon-engine and netmon-api systemd services...${NC}"
        systemctl stop netmon-engine netmon-api || true
    else
        echo -e "${YELLOW}[INFO] Platform systemd services are not active. Skipping stop.${NC}"
    fi
else
    echo -e "[DRY-RUN] Would run: systemctl stop netmon-engine netmon-api"
fi

# 6. Dependency Update & Code Compilation
echo -e "\n${BLUE}--- Step 4/7: Updating System Packages, Dependencies & Building Frontend ---${NC}"
if [[ ${DRY_RUN} -eq 0 ]]; then
    cd "${PROJECT_ROOT}"
    if [[ -d ".git" ]]; then
        echo -e "${GREEN}[INFO] Pulling latest updates from git repository...${NC}"
        git pull origin v3.0.0 || git pull origin 3.0.0 || git pull origin main || git pull || echo -e "${YELLOW}[WARN] Git pull completed with non-zero status. Continuing...${NC}"
    else
        echo -e "${YELLOW}[INFO] Working directory is not a git repository. Skipping git pull.${NC}"
    fi

    # Ensure system dependencies (redis-server, traceroute, libcap2-bin)
    if command -v apt-get &>/dev/null; then
        PACKAGES_TO_CHECK="redis-server traceroute libcap2-bin"
        MISSING_PKGS=""
        for pkg in ${PACKAGES_TO_CHECK}; do
            if ! dpkg -l "${pkg}" 2>/dev/null | grep -q "^ii"; then
                MISSING_PKGS="${MISSING_PKGS} ${pkg}"
            fi
        done

        if [[ -n "${MISSING_PKGS}" ]]; then
            echo -e "${GREEN}[INFO] Installing missing system packages:${MISSING_PKGS}...${NC}"
            apt-get update -qq && apt-get install -y ${MISSING_PKGS} || true
        fi

        # Enable and start Redis
        systemctl enable --now redis-server 2>/dev/null || systemctl enable --now redis 2>/dev/null || true

        # Set network capabilities for raw ICMP traceroute
        TRACEROUTE_BIN=$(command -v traceroute || true)
        if [[ -n "${TRACEROUTE_BIN}" ]] && command -v setcap &>/dev/null; then
            setcap cap_net_raw+ep "${TRACEROUTE_BIN}" || true
        fi
    fi

    # Determine Python virtual environment path
    VENV_PATH=""
    if [[ -d "/opt/netmon/venv" ]]; then
        VENV_PATH="/opt/netmon/venv"
    elif [[ -d "${PROJECT_ROOT}/.venv" ]]; then
        VENV_PATH="${PROJECT_ROOT}/.venv"
    fi

    if [[ -n "${VENV_PATH}" ]]; then
        echo -e "${GREEN}[INFO] Upgrading Python dependencies in ${VENV_PATH}...${NC}"
        "${VENV_PATH}/bin/pip" install --upgrade pip
        "${VENV_PATH}/bin/pip" install -r "${PROJECT_ROOT}/backend/requirements.txt" --upgrade
    else
        echo -e "${YELLOW}[WARN] Virtual environment not found at /opt/netmon/venv or ${PROJECT_ROOT}/.venv. Skipping pip upgrade.${NC}"
    fi

    # Rebuild Vue 3 frontend
    FRONTEND_DIR="${PROJECT_ROOT}/frontend"
    if [[ -d "${FRONTEND_DIR}" && -f "${FRONTEND_DIR}/package.json" ]]; then
        echo -e "${GREEN}[INFO] Rebuilding production Vue 3 frontend bundle...${NC}"
        cd "${FRONTEND_DIR}"
        npm install
        npm run build
        cd "${PROJECT_ROOT}"
    fi
else
    echo -e "[DRY-RUN] Would install redis-server, upgrade pip requirements, and execute npm run build in frontend/"
fi

# 7. Synchronize Production Files
echo -e "\n${BLUE}--- Step 5/7: Synchronizing Codebase & Enforcing Production Structure ---${NC}"
if [[ ${DRY_RUN} -eq 0 ]]; then
    INSTALL_DIR="/opt/netmon/noop"
    if [[ -d "${INSTALL_DIR}" && "${PROJECT_ROOT}" != "${INSTALL_DIR}" ]]; then
        echo -e "${GREEN}[INFO] Syncing repository and built assets to production target ${INSTALL_DIR}...${NC}"
        rsync -a --delete \
            --exclude='.git' \
            --exclude='frontend/node_modules' \
            --exclude='backend/venv' \
            --exclude='backend/.env' \
            --exclude='.env' \
            --exclude='tests' \
            --exclude='pytest.ini' \
            --exclude='scratch' \
            "${PROJECT_ROOT}/" "${INSTALL_DIR}/"
        chown -R netmon:netmon "${INSTALL_DIR}"
    fi
else
    echo -e "[DRY-RUN] Would rsync compiled codebase to /opt/netmon/noop"
fi

# 8. Database Migrations
echo -e "\n${BLUE}--- Step 6/7: Executing Database Schema Migrations ---${NC}"
if [[ ${DRY_RUN} -eq 0 ]]; then
    cd "${PROJECT_ROOT}/backend"
    ALEMBIC_BIN=""
    if [[ -n "${VENV_PATH:-}" && -f "${VENV_PATH}/bin/alembic" ]]; then
        ALEMBIC_BIN="${VENV_PATH}/bin/alembic"
    elif [[ -f "/opt/netmon/venv/bin/alembic" ]]; then
        ALEMBIC_BIN="/opt/netmon/venv/bin/alembic"
    elif [[ -f "${PROJECT_ROOT}/.venv/bin/alembic" ]]; then
        ALEMBIC_BIN="${PROJECT_ROOT}/.venv/bin/alembic"
    fi

    if [[ -d "${PROJECT_ROOT}/backend/migrations" && -n "${ALEMBIC_BIN}" ]]; then
        echo -e "${GREEN}[INFO] Running Alembic schema migration (alembic upgrade head)...${NC}"
        PYTHONPATH="${PROJECT_ROOT}:${PROJECT_ROOT}/backend" "${ALEMBIC_BIN}" -c "${PROJECT_ROOT}/backend/alembic.ini" upgrade head || true
        
        PYTHON_BIN="$(dirname "${ALEMBIC_BIN}")/python"
        if [[ -f "${PYTHON_BIN}" ]]; then
            echo -e "${GREEN}[INFO] Verifying default admin account seeding...${NC}"
            PYTHONPATH="${PROJECT_ROOT}:${PROJECT_ROOT}/backend" "${PYTHON_BIN}" -m app.seed_admin || true
        fi
    fi
    cd "${PROJECT_ROOT}"
else
    echo -e "[DRY-RUN] Would execute: alembic upgrade head"
fi

# 9. Service Unit Refresh, Auto-Start Enablement & Restart
echo -e "\n${BLUE}--- Step 7/7: Refreshing Systemd Units, Enabling Auto-Start & Starting Services ---${NC}"
if [[ ${DRY_RUN} -eq 0 ]]; then
    # Refresh systemd unit files if available in deploy/
    if [[ -f "${PROJECT_ROOT}/deploy/netmon-api.service" ]]; then
        cp "${PROJECT_ROOT}/deploy/netmon-api.service" /etc/systemd/system/
    fi
    if [[ -f "${PROJECT_ROOT}/deploy/netmon-engine.service" ]]; then
        cp "${PROJECT_ROOT}/deploy/netmon-engine.service" /etc/systemd/system/
    fi

    echo -e "${GREEN}[INFO] Reloading systemd daemons and enabling auto-start on boot...${NC}"
    systemctl daemon-reload
    systemctl enable --now redis-server 2>/dev/null || systemctl enable --now redis 2>/dev/null || true
    systemctl enable netmon-api netmon-engine || true
    systemctl restart netmon-api netmon-engine
    systemctl restart nginx || true

    sleep 2
    if systemctl is-active --quiet netmon-api && systemctl is-active --quiet netmon-engine; then
        echo -e "${GREEN}[SUCCESS] All systemd services (netmon-api, netmon-engine) are active, enabled on boot, and healthy.${NC}"
    else
        echo -e "${YELLOW}[WARN] Check service status via: systemctl status netmon-api netmon-engine${NC}"
    fi
else
    echo -e "[DRY-RUN] Would run: systemctl enable & restart redis-server netmon-api netmon-engine"
fi

echo -e "\n${GREEN}========================================================================${NC}"
echo -e "${GREEN}   [UPGRADE COMPLETE] LNMP v3.0.0 Platform upgraded successfully!       ${NC}"
echo -e "${GREEN}   Pre-Upgrade Database Backup Saved At: ${BACKUP_FILE}${NC}"
echo -e "${GREEN}========================================================================${NC}"
