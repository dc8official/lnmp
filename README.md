# LNMP: Network Monitoring Platform v1.5 (Beta)

A high-precision, decoupled network telemetry and monitoring solution designed for continuous endpoint status verification, low-latency ICMP polling, adaptive statistical alerting, and dynamic topology visualization.

---

## Architectural Overview

The platform is decoupled into independent, modular layers to guarantee continuous telemetry collection regardless of client-side dashboard activity or temporary network disruptions:

* **The Monitoring Engine:** A persistent Python daemon managed via `systemd` that performs periodic, high-density ICMP telemetry scans aligned precisely to absolute minute boundaries using native single-threaded `asyncio` concurrency.
* **The Hybrid Adaptive Alert Engine:** A dual-layer evaluation engine combining an in-memory state machine for transient jitter suppression with dynamic statistical baseline tracking. By evaluating live latency against historical time-series bounds via Z-score calculations ($Z = \frac{x - \mu}{\sigma}$), the engine dynamically identifies performance degradation without requiring static thresholds.
* **The Diagnostic & Traceroute Subsystem:** An asynchronous, non-blocking background task worker that triggers immediate path diagnostics on the first detected drop sub-cycle. To protect system resources, executions are throttled via an `asyncio.Semaphore` queue.
* **The Topology & Root Cause Analysis (RCA) Engine:** A sequential discovery pipeline that runs during device onboarding and scheduled midnight passes to build a parent-child network adjacency map. The engine differentiates monitored targets from intermediate transit hops and performs topological RCA: if 100% of downstream monitored children behind an unmonitored transit node fail, the system infers an intermediate transit failure (`INFERRED_DOWN`) and suppresses downstream alert noise.
* **The Telemetry & Diagnostic Datastore:** A hybrid storage design pairing TimescaleDB hypertables and continuous aggregates for high-frequency numeric metrics with a decoupled standard PostgreSQL JSONB table for ephemeral 14-day diagnostic traceroute retention.
* **The Service API:** A lightweight, secure FastAPI framework serving normalized historical telemetry logs, real-time node adjacency graphs (`GET /api/v1/topology`), incident reports, and endpoint governance controls.
* **The Dashboard UI:** A dynamic, high-contrast Vue 3 (Vite) interface styled using PrimeVue and custom CSS properties. Features interactive RTT visualizations, dark/light theme switching, endpoint-level diagnostic toggles, and an interactive `vis-network` topology map with physics stabilization to eliminate canvas jitter.

---

## Technical Stack

* **Backend:** Python 3.10+, FastAPI, SQLAlchemy, Alembic (Migrations), Native `asyncio`
* **Database Layer:** PostgreSQL 14+ with TimescaleDB Extension (Hypertables & Continuous Aggregates)
* **Frontend:** Vue 3 (Composition API), Vite, PrimeVue (Aura Theme Preset), Chart.js, `vis-network`
* **System Layer:** Linux `systemd`, Native Raw Sockets (`CAP_NET_RAW` capability), System `traceroute`

---

## Key Features in v1.5

| Feature Module | Technical Mechanism | Operational Benefit |
| --- | --- | --- |
| **Adaptive Thresholds** | TimescaleDB Continuous Aggregates + In-Memory Z-Score ($Z > 3.0$) | Eliminates false alerts by adjusting latency baselines to match time-of-day traffic patterns. |
| **Automated Diagnostics** | Async `traceroute` execution on initial sub-cycle drop | Captures microsecond-level transit path failures before network routing reconverges. |
| **Topological RCA** | Parent-child graph parsing with intermediate transit inference | Pinpoints upstream network link drops and silences cascading downstream alerts. |
| **Decoupled Data Storage** | Dedicated JSONB table with automated 14-day cleanup worker | Keeps core time-series hypertables fast and query-optimized while preserving diagnostic traces. |
| **Granular Endpoint Control** | Flags: `allow_incident_trace`, `allow_topology_discovery`, `manual_parent_id` | Prevents CPU storms and control-plane traffic overload on sensitive low-bandwidth hardware. |

---

## Recommended System Specifications

### Hardware Requirements

* **CPU:** 1 vCPU (minimum), 2+ Cores (recommended for polling hundreds of nodes concurrently and processing background traceroutes).
* **Memory:** 1 GB RAM (minimum), 2 GB+ RAM (recommended to accommodate TimescaleDB caching, API queries, and in-memory baseline lookup maps).
* **Storage:** 10 GB+ SSD space (dependent on metric retention windows and number of monitored hosts).

### Software Requirements

* **Operating System:** Ubuntu 22.04 LTS or 24.04 LTS (strongly recommended and fully tested).
* **Runtime:** Python 3.10+ and Node.js 18+ (for building/serving frontend assets).
* **Database Engine:** PostgreSQL 14+ with TimescaleDB extension enabled (required for time-series hypertable partitioning and continuous aggregates).

---

## System Time Zone Configuration

> [!IMPORTANT]
> **Server Operating Time Zone:**
> Before deploying the platform, verify and configure the operating time zone of the Linux server to match your local time zone.
> Because the backend daemon, TimescaleDB aggregates, and midnight discovery workers process telemetry events relative to the host operating system clock, ensuring correct clock localization is essential for accurate data logging, baseline grouping, and UI dashboard queries.

Check and update your Linux server time zone using standard system utilities:

```bash
# View current system timezone and clock status
timedatectl

# List all available timezones
timedatectl list-timezones

# Set to your preferred timezone (e.g., Africa/Lagos for GMT+1)
sudo timedatectl set-timezone Africa/Lagos

```

---

## Getting Started (Production Deployment)

For production deployments, the installation package requires elevated administrative privileges. Ensure you elevate your session before beginning:

```bash
sudo -i

```

### 1. Retrieve the Repository

Clone the official repository into your operational workspace and navigate into the project directory:

```bash
git clone https://github.com/dc8official/lnmp.git
cd lnmp

```

### 2. Automatic System Installation

Navigate to the `deploy` folder, grant execution permissions to the installation script, and run it to configure dependencies, database migrations, TimescaleDB views, frontend assets, and background `systemd` daemons:

```bash
cd deploy
./install.sh

```

### 3. Uninstalling the Platform

To remove platform services, database schemas, and associated background daemon configurations:

```bash
cd deploy
./uninstall.sh

```

---

## License & Authorship

Core Architecture designed and authored by **Kenneth Nnorom**.

Website: [kennethnnorom.com](https://kennethnnorom.com) | LinkedIn: [linkedin.com/in/kennethnnorom](https://www.google.com/search?q=https://linkedin.com/in/kennethnnorom)

This project is licensed under the terms of the **Apache License 2.0**. See the [LICENSE] file for complete details.
