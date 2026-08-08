# LNMP Deployment & Operations Guide

This guide details the procedures for installing, maintaining, and upgrading the Network Monitoring Platform (LNMP) v1.5 on a production Linux server.

## 1. System Requirements

- **OS:** Ubuntu 22.04 LTS or 24.04 LTS
- **Hardware (Minimum for Production):** 2 vCPUs, 2 GB RAM, 25 GB SSD. (2 GB RAM is required to prevent OOM errors during `npm run build` and TimescaleDB caching).
- **Network Permissions:** The `netmon-engine` daemon requires `CAP_NET_RAW` capability to construct and send raw ICMP packets.

## 2. Initial Installation

The deployment is fully automated via the `install.sh` script located in the `deploy/` directory.

```bash
sudo -i
git clone https://github.com/dc8official/lnmp.git
cd lnmp/deploy
./install.sh
```

**What the installer does:**
1. Installs system dependencies (Python 3.10+, Node.js 18+, PostgreSQL 14, Nginx).
2. Installs and configures the **TimescaleDB** PostgreSQL extension.
3. Sets up the Python virtual environment and installs `backend/requirements.txt`.
4. Executes `npm install` and `npm run build` in the `frontend/` directory.
5. Deploys the Nginx reverse proxy configuration (`nginx.conf.template`).
6. Configures log rotation via `/etc/logrotate.d/netmon`.
7. Installs and enables the `netmon-api` and `netmon-engine` systemd services.

## 3. Systemd Services

LNMP runs as two separate background services:

### API Service (`netmon-api.service`)
- **Role:** Serves the FastAPI application using Uvicorn.
- **Port:** Binds locally to `127.0.0.1:8000` (Nginx proxies port 80/443 to this).
- **Restart Command:** `sudo systemctl restart netmon-api`

### Engine Service (`netmon-engine.service`)
- **Role:** The infinite-loop daemon that performs the ICMP polling on the absolute minute boundary.
- **Restart Command:** `sudo systemctl restart netmon-engine`

### Checking Service Logs
Logs are output to `syslog` and `/var/log/netmon/`. You can view live daemon logs using `journalctl`:
```bash
# View live API logs
sudo journalctl -u netmon-api -f

# View live Engine polling logs
sudo journalctl -u netmon-engine -f
```

## 4. Upgrading the Platform

To upgrade an existing installation to the latest version on the `main` branch, use the zero-data-loss upgrade script:

```bash
sudo -i
cd /opt/netmon/deploy
./upgrade.sh
```

**The upgrade sequence:**
1. Generates a full `pg_dump` of the PostgreSQL database to `/var/backups/netmon/`.
2. Gracefully stops the `systemd` daemons.
3. Pulls the latest git repository changes.
4. Upgrades Python and Node.js dependencies.
5. Runs Alembic database migrations (`alembic upgrade head`).
6. Restarts the daemons and Nginx.

## 5. Uninstall & Cleanup

To completely remove the platform from the server (including dropping the database):

```bash
sudo -i
cd /opt/netmon/deploy
./uninstall.sh --force
```

## 6. Password Resets (CLI)

If you lose access to the Admin account, you can force a password reset directly from the server CLI using the provided script:

```bash
cd /opt/netmon/deploy
sudo ./reset-admin-password.sh <username> <new_password>
```
