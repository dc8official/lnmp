# LNMP: Network Monitoring Platform v2.0 (Beta)

A high-precision, decoupled network telemetry and monitoring solution designed for continuous endpoint status verification, low-latency ICMP polling, adaptive statistical alerting, automated root-cause analysis (RCA), and dynamic topology visualization with crossing-free layout routing.

---

## Architectural Overview

The platform is decoupled into independent, modular layers to guarantee continuous telemetry collection regardless of client-side dashboard activity or temporary network disruptions:

* **The Monitoring Engine:** A persistent Python daemon managed via `systemd` that performs periodic, high-density ICMP telemetry scans aligned precisely to absolute minute boundaries. Features a top-of-minute database write semaphore (`asyncio.Semaphore(15)`) to eliminate connection pool thundering herds.
* **The Hybrid Adaptive Alert Engine:** A dual-layer evaluation engine combining an in-memory state machine for transient jitter suppression with dynamic statistical baseline tracking. By evaluating live latency against historical time-series bounds via Z-score calculations ($Z = \frac{x - \mu}{\sigma}$), the engine dynamically identifies performance degradation without requiring static thresholds.
* **The Diagnostic & Traceroute Subsystem:** An asynchronous, non-blocking background task worker that triggers immediate path diagnostics on the first detected drop sub-cycle. Executions are throttled via an `asyncio.Semaphore` queue to protect system resources.
* **The Topology & Root Cause Analysis (RCA) Engine:** A sequential discovery pipeline that runs during device onboarding and scheduled midnight passes to build a parent-child network adjacency map. Differentiates monitored targets from intermediate transit hops and performs topological RCA (`INFERRED_DOWN`) to suppress cascading alert storms.
* **Interactive Crossing-Free Topology Map:** A Vue 3 Vis-Network visualizer implementing the **Sugiyama (1981)** barycenter crossing reduction framework and **Gansner / DOT (1993)** coordinate heuristics (`edgeMinimization`, `blockShifting`, `parentCentralization`, directional tangent channeling) with dynamic **Horizontal (LR) ⇄ Vertical (UD)** layout switching.
* **The Telemetry & Diagnostic Datastore:** A hybrid storage design pairing TimescaleDB hypertables with **7-day chunk compression** (90%+ disk savings) and **automated continuous aggregate refresh policies** for sub-millisecond query performance over multi-year deployments.
* **Security & Session Governance:** Features **sliding 2-hour inactivity timeouts**, **token-based concurrent session quotas** (max 2 active sessions with FIFO rotation), and **IP-scoped failed login lockouts** (`<Client_IP>:<Username>`) to protect corporate NATs and VPNs from credential brute-force attacks.
* **Observability & Logging Suite:** Dual console (`systemd journalctl`) and **150MB auto-rotating log files** (`/var/log/netmon/api.log`, `engine.log`, `error.log`) with global FastAPI request latency and security diagnostic middleware.

---

## Detailed Documentation

For a deeper dive into specific components of the platform, please refer to the comprehensive guides in the `docs/` directory:

* **[Architecture Overview](docs/architecture.md):** In-depth explanation of decoupled engines, TimescaleDB compression, Sugiyama topology routing, and RCA inference logic.
* **[User & Operator Guide](docs/user-guide.md):** Instructions for onboarding devices, browser autofill, horizontal/vertical topology views, and interpreting Z-Score baselines.
* **[API Reference](docs/api-reference.md):** Complete guide to FastAPI REST endpoints, JSON payloads, and RBAC token claims.
* **[Deployment & Operations](docs/deployment.md):** Step-by-step production installation, systemd auto-start configuration, log rotation, and zero-downtime upgrades.
* **[Developer Guide](docs/developer-guide.md):** Local setup instructions for Vite and Uvicorn, plus guidelines for contributing via Alembic migrations.

---

## Technical Stack

* **Backend:** Python 3.10+, FastAPI, SQLAlchemy, Alembic (Migrations), Native `asyncio`
* **Database Layer:** PostgreSQL 14+ with TimescaleDB Extension (Hypertables, 7-Day Chunk Compression, Continuous Aggregates)
* **Frontend:** Vue 3 (Composition API), Vite, PrimeVue (Aura Theme Preset), Chart.js, `vis-network` (Sugiyama Crossing Reduction)
* **System Layer:** Linux `systemd` (with Auto-Start Enablement), Native Raw Sockets (`CAP_NET_RAW` capability), System `traceroute`
* **Logging:** Python `RotatingFileHandler` (~150MB bounded footprint) + `systemd-journald`

---

## Key Features in v2.0 (Beta)

| Feature Module | Technical Mechanism | Operational Benefit |
| --- | --- | --- |
| **Crossing-Free Topology Map** | Sugiyama (1981) Barycenter Reduction + Gansner (1993) Block Shifting | Completely eliminates tangled, crossing wires; centers parent routers above child nodes. |
| **Horizontal ⇄ Vertical Switcher** | Dynamic `layout.hierarchical.direction` (`LR` vs `UD`) toggle | Allows operators to switch between top-to-bottom and widescreen left-to-right layouts with smooth animation. |
| **Browser Password Autofill** | Standard HTML `name` and `autocomplete` attributes | Enables 1-click login and credential saving across Chrome, Edge, Safari, Firefox, and Bitwarden. |
| **Sliding 2-Hour Session Timeout** | Sliding window token & cookie renewal | Active operators are never logged out in the middle of monitoring, while idle tabs expire safely after 120 minutes. |
| **Token-Based Session Limits** | JWT `jti` tracking with in-memory FIFO rotation (Max 2 sessions) | Limits concurrent device logins per user without conflicting with colleagues behind shared office NAT/VPN gateways. |
| **IP-Scoped Lockout Protection** | Isolated failed attempt tracker keyed by `f"{client_ip}:{username}"` | External internet bot scans or single-device glitches only lock out their own IP, leaving legitimate admins unaffected. |
| **TimescaleDB 7-Day Compression** | Native columnar hypertable chunk compression | Reduces disk storage by 90%+ while keeping years of historical telemetry 100% queryable for charts. |
| **Continuous Aggregate Policies** | Automated hourly background refresh with crash catch-up | Accelerates historical baseline queries and saves server RAM during live dashboard usage. |
| **DB Write Semaphore** | `asyncio.Semaphore(15)` in monitoring engine | Eliminates top-of-the-minute connection pool exhaustion when polling 100+ endpoints. |
| **Comprehensive Logging Suite** | Global latency middleware + 150MB auto-rotating files | Full diagnostic transparency into API calls, latency, auth rejections, and state transitions with zero disk bloat. |
| **Bulletproof Lifecycle Scripts** | `install.sh`, `upgrade.sh`, `uninstall.sh` with `systemctl enable` | Zero-downtime upgrades, automatic `config.toml` migrations, and guaranteed auto-start on server boot. |

---

## Recommended System Specifications

### Hardware Sizing Matrix

| Deployment Scale | Monitored Endpoints | CPU Cores | Memory (RAM) | Storage (SSD) | Recommended Use Case |
| --- | --- | --- | --- | --- | --- |
| **Small / Lab** | Up to 100 | 1 vCPU | 2 GB RAM | 10 GB SSD | Home lab, edge monitoring, small office networks. |
| **Medium Enterprise** | 100 – 500 | 2 vCPUs | 4 GB RAM | 25 GB SSD | Branch networks, regional datacenter monitoring. |
| **Large Scale** | 500 – 2,000+ | 4+ vCPUs | 8 GB+ RAM | 50 GB+ NVMe | Multi-site enterprise datacenters & ISP backbones. |

> [!NOTE]
> **v2.0 Resource Dynamics:**
> With **TimescaleDB 7-day chunk compression** enabled, disk storage consumption is reduced by 90%+. The comprehensive logging suite is hard-capped at **~150 MB** on disk. **2 GB RAM is the recommended baseline** to ensure smooth zero-swap database caching, instant API responses, and fast frontend asset builds (`npm run build`).

---

## Getting Started (Production Deployment)

For production deployments, execute with root privileges:

```bash
sudo -i
```

### 1. Retrieve the Repository

```bash
git clone https://github.com/dc8official/lnmp.git
cd lnmp
```

### 2. Automatic System Installation

```bash
cd deploy
./install.sh
```

### 3. Upgrading the Platform (Zero Data Loss)

You can run the upgrade utility from your git clone directory or directly in `/opt/netmon/noop`:

```bash
cd deploy
./upgrade.sh
```

The upgrade utility automatically executes:
1. **Pre-Upgrade Backup**: Dumps a timestamped PostgreSQL SQL backup to `/var/backups/netmon/`.
2. **Smart Config Migration**: Updates `/etc/netmon/config.toml` (e.g. 120m timeout, 2-session limit) without touching database credentials.
3. **Service Pause**: Gracefully pauses background daemons.
4. **Code & Dependency Sync**: Pulls updates, upgrades Python packages, and rebuilds Vue 3 frontend assets.
5. **Database Migrations**: Applies latest Alembic migrations including TimescaleDB compression policies (`alembic upgrade head`).
6. **Systemd Auto-Start Enablement**: Refreshes `.service` units, enables services on boot (`systemctl enable`), and restarts daemons.
7. **Health Check**: Verifies live API status.

### 4. Uninstalling the Platform (Clean Decommission)

To decommission the platform, remove background services, and clean up web routing:

```bash
cd deploy
./uninstall.sh
```

---

## License & Authorship

Core Architecture designed and authored by **Kenneth Nnorom**.

Website: [kennethnnorom.com](https://kennethnnorom.com) | LinkedIn: [linkedin.com/in/kennethnnorom](https://www.google.com/search?q=https://linkedin.com/in/kennethnnorom)

This project is licensed under the terms of the **Apache License 2.0**. See the [LICENSE] file for complete details.
