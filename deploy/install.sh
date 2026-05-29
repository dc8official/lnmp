#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "Starting installation in DRY RUN mode. No changes will be made."
fi

execute() {
    local msg="$1"
    shift
    if [ "$DRY_RUN" = true ]; then
        echo "[DRY RUN] $msg"
        echo "[DRY RUN] Command: $*"
    else
        echo "$msg"
        "$@"
    fi
}

echo "========================================"
echo "noop Platform Installation"
echo "========================================"

# Step 1: Check root
if [ "$EUID" -ne 0 ] && [ "$DRY_RUN" = false ]; then
    echo "Error: This script must be run as root."
    exit 1
fi

# Step 3: Install system packages
echo "Checking system packages..."
PACKAGES="postgresql postgresql-contrib timescaledb-postgresql-16 python3.11 python3.11-venv python3-pip nginx certbot python3-certbot-nginx"
MISSING_PACKAGES=""
for pkg in $PACKAGES; do
    if ! dpkg -l | grep -q "^ii  $pkg "; then
        MISSING_PACKAGES="$MISSING_PACKAGES $pkg"
    fi
done

if [ -n "$MISSING_PACKAGES" ]; then
    execute "Installing missing packages: $MISSING_PACKAGES" apt-get update
    execute "Installing packages" apt-get install -y $MISSING_PACKAGES
else
    echo "All system packages are already installed."
fi

# Step 4: Create system user
if id "netmon" &>/dev/null; then
    echo "User 'netmon' already exists."
else
    execute "Creating system user 'netmon'" useradd -r -s /usr/sbin/nologin netmon
fi

# Step 5: Create directories
DIRS="/opt/netmon /etc/netmon /var/log/netmon /var/backups/netmon"
for d in $DIRS; do
    if [ ! -d "$d" ]; then
        execute "Creating directory $d" mkdir -p "$d"
    fi
    execute "Setting ownership for $d" chown netmon:netmon "$d"
done

# Step 6: Copy project files
if [ -d "/opt/netmon/noop" ]; then
    execute "Removing old project files" rm -rf /opt/netmon/noop
fi
execute "Copying project files to /opt/netmon/noop" cp -r ../noop /opt/netmon/
execute "Setting ownership of project files" chown -R netmon:netmon /opt/netmon/noop

# Step 7 & 8: Create Python venv and install requirements
if [ ! -d "/opt/netmon/venv" ]; then
    execute "Creating Python virtual environment" python3.11 -m venv /opt/netmon/venv
fi
execute "Setting ownership of venv" chown -R netmon:netmon /opt/netmon/venv
execute "Installing Python dependencies" sudo -u netmon /opt/netmon/venv/bin/pip install -r /opt/netmon/noop/backend/requirements.txt

# Build Vue frontend
echo "Checking frontend build..."
if [ ! -d "/opt/netmon/noop/frontend/dist" ]; then
    execute "Installing frontend npm dependencies" \
        bash -c "cd /opt/netmon/noop/frontend && npm install"
    execute "Building Vue frontend" \
        bash -c "cd /opt/netmon/noop/frontend && npm run build"
    execute "Setting frontend ownership" \
        chown -R netmon:netmon /opt/netmon/noop/frontend/dist
else
    echo "Frontend dist already exists. Skipping build."
fi

# Step 9 & 10: Environment Configuration
ENV_FILE="/etc/netmon/netmon.env"
if [ ! -f "$ENV_FILE" ]; then
    if [ "$DRY_RUN" = false ]; then
        read -s -p "Enter new database password for netmon: " DB_PASS
        echo ""
        read -s -p "Enter new application secret key: " SECRET_KEY
        echo ""
        read -p "Enter domain name for Nginx: " DOMAIN_NAME
        
        echo "NETMON_DB_PASSWORD=$DB_PASS" > "$ENV_FILE"
        echo "NETMON_SECRET_KEY=$SECRET_KEY" >> "$ENV_FILE"
        echo "DOMAIN_NAME=$DOMAIN_NAME" >> "$ENV_FILE"
        
        chmod 640 "$ENV_FILE"
        chown root:netmon "$ENV_FILE"
        echo "Environment file created."
    else
        echo "[DRY RUN] Would prompt for DB_PASS, SECRET_KEY, DOMAIN_NAME and create $ENV_FILE"
    fi
else
    echo "Environment file already exists at $ENV_FILE."
fi

# Step 11 & 12: PostgreSQL Setup
if [ "$DRY_RUN" = false ]; then
    if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='netmon_user'" | grep -q 1; then
        echo "Creating PostgreSQL user..."
        if [ -z "${DB_PASS:-}" ]; then
            DB_PASS=$(grep NETMON_DB_PASSWORD "$ENV_FILE" | cut -d '=' -f2)
        fi
        sudo -u postgres psql -c "CREATE USER netmon_user WITH PASSWORD '${DB_PASS}';"
    else
        echo "PostgreSQL user 'netmon_user' already exists."
    fi

    if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='netmon'" | grep -q 1; then
        echo "Creating PostgreSQL database..."
        sudo -u postgres psql -c "CREATE DATABASE netmon OWNER netmon_user;"
        echo "Enabling TimescaleDB extension..."
        sudo -u postgres psql -d netmon -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
    else
        echo "PostgreSQL database 'netmon' already exists."
    fi
else
    echo "[DRY RUN] Would create PostgreSQL user and database 'netmon', and enable timescaledb extension."
fi

# Step 13: Run Alembic migrations
execute "Running Alembic migrations" sudo -u netmon bash -c "cd /opt/netmon/noop/backend && /opt/netmon/venv/bin/alembic upgrade head"

# Step 14: Systemd files
for service in netmon-engine netmon-api; do
    execute "Installing ${service}.service" cp "/opt/netmon/noop/deploy/${service}.service" /etc/systemd/system/
done
execute "Reloading systemd daemon" systemctl daemon-reload
execute "Enabling netmon services" systemctl enable netmon-engine netmon-api
if [ "$DRY_RUN" = false ]; then
    execute "Restarting netmon services" systemctl restart netmon-engine netmon-api || true
fi

# Step 15: Nginx config
if [ "$DRY_RUN" = false ]; then
    DOMAIN=$(grep DOMAIN_NAME "$ENV_FILE" | cut -d '=' -f2)
    sed "s/YOUR_DOMAIN/$DOMAIN/g" /opt/netmon/noop/deploy/nginx.conf.template > /etc/nginx/sites-available/netmon
    ln -sf /etc/nginx/sites-available/netmon /etc/nginx/sites-enabled/
    nginx -t && systemctl reload nginx
    echo "Nginx configuration generated and reloaded."
else
    echo "[DRY RUN] Would generate Nginx configuration and reload."
fi

# Step 16: Logrotate config
execute "Installing logrotate configuration" cp /opt/netmon/noop/deploy/logrotate.conf /etc/logrotate.d/netmon

# Step 17: Initial Admin User
if [ "$DRY_RUN" = false ]; then
    read -p "Do you want to create the initial admin user now? (y/n): " CREATE_ADMIN
    if [[ "$CREATE_ADMIN" == "y" || "$CREATE_ADMIN" == "Y" ]]; then
        read -p "Enter admin username: " ADMIN_USER
        read -s -p "Enter admin password: " ADMIN_PASS
        echo ""
        
        cat <<'PYEOF' > /tmp/create_admin.py
import asyncio
import os
from app.database import AsyncSessionLocal
from app.services.auth_service import hash_password
from sqlalchemy import text

async def create_user():
    username = os.environ["ADMIN_USER"]
    password = os.environ["ADMIN_PASS"]
    async with AsyncSessionLocal() as db:
        role_res = await db.execute(
            text("SELECT id FROM roles WHERE role_name = 'ADMIN'")
        )
        role_id = role_res.scalar()
        if not role_id:
            print("ADMIN role not found. Run migrations first.")
            return
        hashed = hash_password(password)
        await db.execute(
            text(
                "INSERT INTO users (username, password_hash, role_id) "
                "VALUES (:u, :p, :r) ON CONFLICT DO NOTHING"
            ),
            {"u": username, "p": hashed, "r": str(role_id)},
        )
        await db.commit()
        print("Admin user created successfully.")

asyncio.run(create_user())
PYEOF
        ADMIN_USER="$ADMIN_USER" ADMIN_PASS="$ADMIN_PASS" \
        sudo -u netmon bash -c \
            "cd /opt/netmon/noop/backend && \
             /opt/netmon/venv/bin/python /tmp/create_admin.py"
        rm -f /tmp/create_admin.py
    fi
else
    echo "[DRY RUN] Would prompt for and create initial admin user."
fi

# Step 18: Summary
echo "========================================"
echo "Installation script completed."
if [ "$DRY_RUN" = true ]; then
    echo "This was a DRY RUN. No changes were made to the system."
else
    echo "Please verify the status of the services:"
    echo "  systemctl status netmon-engine"
    echo "  systemctl status netmon-api"
fi
echo "========================================"
