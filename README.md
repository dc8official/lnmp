# LNMP — Network  Monitoring Platform v1.0(beta)

A high-precision, decoupled network telemetry and monitoring solution designed for continuous endpoint status verification, low-latency ICMP polling, and real-time state visualization.

## Architectural Overview
The platform is decoupled into independent layers to guarantee continuous telemetry collection regardless of client-side dashboard activity:
* **The Monitoring Engine:** A persistent Python daemon managed via systemd that performs periodic, high-density ICMP telemetry scans aligned precisely to absolute minute boundaries.
* **The Verification State Machine:** A local processing loop that evaluates status transitions and filters out transient network jitter via configurable validation confirmation thresholds.
* **The Telemetry Database:** A relational schema designed to persist per-minute endpoint events, detailed operational states, health metrics, and round-trip times (RTT) with time-series indexing.
* **The Service API:** A lightweight, secure FastAPI framework serving normalized telemetry historical logs, incidents reports, and administrative management endpoints.
* **The Dashboard UI:** A dynamic, high-contrast Vue 3 (Vite) interface styled using CSS custom properties with fully responsive dark/light theme options, real-time RTT visualizations, and sub-hour custom query range filters.

---

## Technical Stack
* **Backend:** Python 3.10+, FastAPI, SQLAlchemy, Alembic (Migrations)
* **Database:** PostgreSQL or SQLite
* **Frontend:** Vue 3, Vite, PrimeVue (Aura Theme Preset), Chart.js
* **System Layer:** Linux systemd, Native Raw Sockets (`CAP_NET_RAW` capability)

---

## Recommended System Specifications

### Hardware Requirements
* **CPU:** 1 vCPU (minimum), 2+ Cores (recommended for polling hundreds of nodes concurrently).
* **Memory:** 1 GB RAM (minimum), 2 GB+ RAM (recommended to accommodate caching, API requests, and DB indexing).
* **Storage:** 10 GB+ SSD space (highly dependent on logging retention policies and number of tracked hosts).

### Software Requirements
* **Operating System:** Ubuntu 22.04 LTS or 24.04 LTS (strongly recommended and fully tested).
* **Runtime:** Python 3.10+ & Node.js 18+ (for building/serving frontend assets).
* **Database Engine:** PostgreSQL 14+ (recommended for production time-series scalability) or SQLite (for development).

---

## System Time Zone Configuration

> [!IMPORTANT]
> **Server Operating Time Zone:**
> Before deploying the platform, users **must** verify and configure the operating time zone of the Linux server to match their preferred local time zone. 
> Since the backend daemon and database record and store all telemetry events relative to the host server's local operating system time zone, ensuring the server clock is correctly localized is crucial to accurately logging, querying, and displaying historical telemetry data.
>
> You can check and update your Linux server's timezone using standard tools:
> ```bash
> # View current system timezone and clock status
> timedatectl
>
> # List all available timezones
> timedatectl list-timezones
>
> # Set to your preferred timezone (e.g., Africa/Lagos for GMT+1)
> sudo timedatectl set-timezone Africa/Lagos
> ```

---

## Getting Started (Production Deployment)

For production deployments, the package is designed to run best when configured as root. Ensure you elevate your session before beginning:
```bash
sudo -i
```

### 1. Retrieve the Repository
Clone the official repository into your system's operational space and enter the downloaded directory:
```bash
git clone https://github.com/dc8official/lnmp.git
cd lnmp
```

### 2. Automatic System Installation
Navigate to the `deploy` folder, ensure the installation script has execution permissions, and run it to set up all dependencies, database configurations, frontend visual builds, and background daemons:
```bash
cd deploy
./install.sh
```

### 3. Uninstalling the Platform
If you need to completely remove the platform services, database schemas, and associated system daemon configurations, navigate to the `deploy` folder and execute the provided uninstallation script:
```bash
cd deploy
./uninstall.sh
```

---

## License & Authorship
Core Architecture designed and authored by **Kenneth Nnorom**.  
This project is licensed under the terms of the **Apache License 2.0**. See the [LICENSE] file for complete details.
