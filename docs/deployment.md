# LNMP Deployment & Operations Guide — Version 2.0 (Beta)

This guide details the procedures for installing, maintaining, and upgrading the Network Monitoring Platform (LNMP) v2.0 (Beta) on a production Linux server.

---

## 1. System Requirements

- **OS:** Ubuntu 22.04 LTS or 24.04 LTS
- **Hardware (Minimum for Production):** 2 vCPUs, 2 GB RAM, 10–25 GB SSD. (TimescaleDB 7-day chunk compression reduces storage growth by 90%+).
- **Network Permissions:** The `netmon-engine` daemon requires `CAP_NET_RAW` capability to construct and send raw ICMP packets.

---

## 2. Initial Installation

The deployment is fully automated via the `install.sh` script located in the `deploy/` directory.

```bash
sudo -i
git clone https://github.com/dc8official/lnmp.git
cd lnmp/deploy
./install.sh
```

**What the installer does:**
1. Installs system dependencies (Python 3.10+, Node.js 18+, PostgreSQL 14+, TimescaleDB, Nginx).
2. Sets up Python virtual environment (`/opt/netmon/venv`) and installs dependencies.
3. Builds the Vue 3 production bundle (`npm run build`).
4. Generates `/etc/netmon/config.toml` (configured with 120-minute session timeout and 2 concurrent session limit).
5. Deploys Nginx reverse proxy configuration.
6. Installs and **enables** `netmon-api` and `netmon-engine` systemd services (`systemctl enable`) to guarantee auto-start on server boot.

---

## 3. Systemd Services & Auto-Start

LNMP runs as two separate background services:

### API Service (`netmon-api.service`)
- **Role:** Serves the FastAPI application with async access latency logging and security diagnostics.
- **Port:** Binds locally to `127.0.0.1:8000` (Nginx proxies port 80/443 to this).
- **Restart Command:** `sudo systemctl restart netmon-api`

### Engine Service (`netmon-engine.service`)
- **Role:** High-density ICMP polling daemon aligned to absolute minute boundaries with `asyncio.Semaphore(15)` write throttling.
- **Restart Command:** `sudo systemctl restart netmon-engine`

### Auto-Start Verification:
```bash
sudo systemctl is-enabled netmon-api netmon-engine
# Should output: enabled
```

---

## 4. Comprehensive Logging & Inspection

Application logs are written simultaneously to **systemd journal** and **150MB auto-rotating log files**:

| Log Target | Path | Rotation Bounds |
|---|---|---|
| **API Server Logs** | `/var/log/netmon/api.log` | 10 MB per file (5 backups = 60 MB max) |
| **Monitoring Engine Logs** | `/var/log/netmon/engine.log` | 10 MB per file (5 backups = 60 MB max) |
| **Dedicated Error Logs** | `/var/log/netmon/error.log` | 10 MB per file (3 backups = 30 MB max) |

### Live Log Commands:
```bash
# Live API request and latency logs
sudo journalctl -u netmon-api -f

# Live monitoring engine state transitions & ping logs
sudo journalctl -u netmon-engine -f

# View errors only across the platform
sudo journalctl -u netmon-api -p err -e
tail -f /var/log/netmon/error.log
```

---

## 5. Upgrading the Platform (Zero-Downtime)

You can run the upgrade utility from your git clone directory or directly in `/opt/netmon/noop`:

```bash
# From git clone
cd ~/noop
sudo ./deploy/upgrade.sh

# Or directly in /opt/netmon/noop
cd /opt/netmon/noop
sudo git pull
sudo ./deploy/upgrade.sh
```

**The upgrade sequence:**
1. Generates a timestamped `pg_dump` of the PostgreSQL database to `/var/backups/netmon/`.
2. Smartly patches `/etc/netmon/config.toml` (migrating `session_timeout_minutes = 120` and `max_active_sessions_per_user = 2`) without touching database credentials.
3. Gracefully pauses `systemd` daemons.
4. Upgrades Python dependencies and rebuilds the Vue 3 frontend bundle.
5. Runs Alembic database migrations (`alembic upgrade head`) including TimescaleDB compression policies.
6. Refreshes systemd unit files, enables auto-start (`systemctl enable`), and restarts services.
7. Executes a health check to verify live API status.

---

## 6. Decommissioning & Uninstallation

To cleanly remove LNMP, disable background daemons, and remove web routes:

```bash
sudo -i
cd /opt/netmon/deploy
./uninstall.sh
```

The script prompts for confirmation, saves a safety database backup, stops/disables systemd services, and removes Nginx configurations.

---

## 7. Password Resets (CLI)

If you lose access to the Admin account, force a password reset directly from the CLI:

```bash
sudo /opt/netmon/noop/deploy/reset-admin-password.sh <username> <new_password>
```
