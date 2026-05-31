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
        NEW_PASS=$(openssl rand -base64 12 | tr -dc 'a-zA-Z0-9' | head -c 12)
        echo "Auto-generated new password: $NEW_PASS"
    fi
fi

# Execute python reset script inside the virtual environment
sudo -H -u netmon bash -c "
    export NETMON_DB_PASSWORD='$DB_PASS' &&
    export NETMON_SECRET_KEY='$SECRET_KEY' &&
    export PYTHONPATH='/opt/netmon/noop/backend' &&
    /opt/netmon/venv/bin/python - <<'PYEOF'
import asyncio
from app.database import AsyncSessionLocal
from app.services.auth_service import hash_password
from sqlalchemy import text

async def update_admin_password():
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            text(\"SELECT id FROM users WHERE username = 'admin'\")
        )
        if not existing.fetchone():
            print(\"Error: Admin user does not exist in the database.\")
            return
            
        hashed = hash_password('$NEW_PASS')
        await db.execute(
            text(\"UPDATE users SET password_hash = :p, must_change_password = TRUE WHERE username = 'admin'\"),
            {'p': hashed}
        )
        await db.commit()
        print(\"Admin password updated and reset flag set successfully inside the database.\")

asyncio.run(update_admin_password())
PYEOF
"

echo ""
echo "--------------------------------------------------------"
echo "  Updated Admin Credentials"
echo "  Username: admin"
echo "  Password: $NEW_PASS"
echo "--------------------------------------------------------"
