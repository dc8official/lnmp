#!/usr/bin/env bash
# ==============================================================================
# LNMP Network Monitoring Platform v1.5 - Automated Zero-Downtime Upgrade Utility
# ==============================================================================

set -euo pipefail

# Color Palette for Terminal Output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Require Root / Administrative Privileges
if [[ ${EUID} -ne 0 ]]; then
    echo -e "${RED}[ERROR] This script must be executed with root privileges (e.g., sudo -i or ./upgrade.sh as root).${NC}" >&2
    exit 1
fi

echo -e "${BLUE}========================================================================${NC}"
echo -e "${BLUE}       LNMP Network Monitoring Platform v1.5 - System Upgrade Utility    ${NC}"
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

echo -e "\n${BLUE}--- Step 1/6: Executing Pre-Upgrade Database Backup ---${NC}"
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

# 4. Service Pause
echo -e "\n${BLUE}--- Step 2/6: Gracefully Pausing Platform Background Daemons ---${NC}"
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

# 5. Code Sync & Sync Exclusions
echo -e "\n${BLUE}--- Step 3/6: Synchronizing Codebase & Enforcing Production Exclusions ---${NC}"
if [[ ${DRY_RUN} -eq 0 ]]; then
    cd "${PROJECT_ROOT}"
    if [[ -d ".git" ]]; then
        echo -e "${GREEN}[INFO] Pulling latest updates from git repository...${NC}"
        git pull origin main || git pull || echo -e "${YELLOW}[WARN] Git pull completed with non-zero status. Continuing...${NC}"
    else
        echo -e "${YELLOW}[INFO] Working directory is not a git repository. Skipping git pull.${NC}"
    fi

    INSTALL_DIR="/opt/netmon/noop"
    if [[ -d "${INSTALL_DIR}" && "${PROJECT_ROOT}" != "${INSTALL_DIR}" ]]; then
        echo -e "${GREEN}[INFO] Syncing repository files to production target ${INSTALL_DIR}...${NC}"
        rsync -a --delete \
            --exclude='.git' \
            --exclude='frontend/node_modules' \
            --exclude='backend/venv' \
            --exclude='tests' \
            --exclude='pytest.ini' \
            --exclude='scratch' \
            "${PROJECT_ROOT}/" "${INSTALL_DIR}/"
        chown -R netmon:netmon "${INSTALL_DIR}"
    fi
else
    echo -e "[DRY-RUN] Would pull git changes and rsync files to /opt/netmon/noop excluding tests/, pytest.ini, scratch/"
fi

# 6. Dependency Update
echo -e "\n${BLUE}--- Step 4/6: Updating Python & Frontend Dependencies ---${NC}"
if [[ ${DRY_RUN} -eq 0 ]]; then
    # Python virtual environment update
    VENV_PATH="${PROJECT_ROOT}/.venv"
    if [[ -d "${VENV_PATH}" ]]; then
        echo -e "${GREEN}[INFO] Upgrading Python dependencies in ${VENV_PATH}...${NC}"
        "${VENV_PATH}/bin/pip" install --upgrade pip
        "${VENV_PATH}/bin/pip" install -r "${PROJECT_ROOT}/backend/requirements.txt" --upgrade
    else
        echo -e "${YELLOW}[WARN] Virtual environment not found at ${VENV_PATH}. Skipping pip upgrade.${NC}"
    fi

    # Frontend build
    FRONTEND_DIR="${PROJECT_ROOT}/frontend"
    if [[ -d "${FRONTEND_DIR}" && -f "${FRONTEND_DIR}/package.json" ]]; then
        echo -e "${GREEN}[INFO] Rebuilding production Vue 3 frontend bundle...${NC}"
        cd "${FRONTEND_DIR}"
        npm install
        npm run build
        cd "${PROJECT_ROOT}"
    fi
else
    echo -e "[DRY-RUN] Would upgrade pip requirements and execute npm run build in frontend/"
fi

# 7. Database Migrations
echo -e "\n${BLUE}--- Step 5/6: Executing Database Schema Migrations ---${NC}"
if [[ ${DRY_RUN} -eq 0 ]]; then
    cd "${PROJECT_ROOT}"
    if [[ -d "${PROJECT_ROOT}/backend/migrations" && -f "${PROJECT_ROOT}/.venv/bin/alembic" ]]; then
        echo -e "${GREEN}[INFO] Running Alembic schema migration (alembic upgrade head)...${NC}"
        PYTHONPATH="${PROJECT_ROOT}:${PROJECT_ROOT}/backend" "${PROJECT_ROOT}/.venv/bin/alembic" -c "${PROJECT_ROOT}/backend/alembic.ini" upgrade head
    else
        echo -e "${YELLOW}[INFO] Alembic migration configuration not found. Skipping DB migration.${NC}"
    fi
else
    echo -e "[DRY-RUN] Would execute: alembic upgrade head"
fi

# 8. Service Restart & Verification
echo -e "\n${BLUE}--- Step 6/6: Restarting & Verifying Platform Services ---${NC}"
if [[ ${DRY_RUN} -eq 0 ]]; then
    if systemctl list-unit-files | grep -q "netmon-api.service"; then
        echo -e "${GREEN}[INFO] Reloading systemd daemons and starting services...${NC}"
        systemctl daemon-reload
        systemctl start netmon-api netmon-engine
        systemctl restart nginx || true

        sleep 2
        if systemctl is-active --quiet netmon-api && systemctl is-active --quiet netmon-engine; then
            echo -e "${GREEN}[SUCCESS] All systemd services (netmon-api, netmon-engine) are active and healthy.${NC}"
        else
            echo -e "${YELLOW}[WARN] One or more services failed to start cleanly. Check systemctl status netmon-api netmon-engine.${NC}"
        fi
    else
        echo -e "${YELLOW}[INFO] Systemd services not registered. Please start services manually if using non-systemd setup.${NC}"
    fi
else
    echo -e "[DRY-RUN] Would run: systemctl start netmon-api netmon-engine"
fi

echo -e "\n${GREEN}========================================================================${NC}"
echo -e "${GREEN}   [UPGRADE COMPLETE] LNMP v1.5 Platform upgraded successfully!          ${NC}"
echo -e "${GREEN}   Pre-Upgrade Database Backup Saved At: ${BACKUP_FILE}${NC}"
echo -e "${GREEN}========================================================================${NC}"
