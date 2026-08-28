# LNMP Changelog & Evolutionary Architecture

All notable technical changes, architectural upgrades, security enhancements, and stability milestones for the Lightweight Network Monitoring Platform (LNMP) are documented in this file.

The versioning format follows [Semantic Versioning](https://semver.org/).

---

## [Version 2.0 (Beta)] — Current Release

### 🕸️ Interactive Topology Map & Crossing-Free Layout (Approach A)
* **BFS DAG Longest-Path Layering ($L(v) = \max(L(u) + 1)$)**: Implemented exact topological depth tiering in both the backend (`topology.py`) and frontend (`TopologyMap.vue`). Automatically assigns discrete hop-count tiers to all nodes, consolidating shared routes and completely eliminating false diagonal links.
* **4-Phase Sugiyama & Gansner Engine**: Integrated Sugiyama (1981) barycenter crossing reduction (`edgeMinimization: true`), Gansner (1993) coordinate alignment (`blockShifting: true`, `parentCentralization: true`), and directional tangent channeling (`cubicBezier`).
* **Dynamic Orientation Switcher**: Interactive toolbar toggle between **Vertical (Top-to-Bottom `UD`)** and **Horizontal (Left-to-Right `LR`)** layouts with smooth canvas transitions.

### 🛡️ 24/7 Database & Engine Stability Hardening
* **TimescaleDB 7-Day Chunk Compression**: Migration `0005_v2_0_timescale_stability.py` enables native hypertable compression on `endpoint_events` older than 7 days, reducing database disk usage by 90%+ while keeping historical charts and reports 100% queryable.
* **Continuous Aggregate Refresh Policy**: Automatic hourly background refresh policy on `node_historical_baselines` with crash-recovery catch-up on server reboot.
* **Top-of-Minute DB Write Semaphore**: Enforced `asyncio.Semaphore(15)` in `monitoring/engine.py` to prevent PostgreSQL connection pool exhaustion during concurrent top-of-minute ping commits.
* **Automated Retention Purging**: Background worker purges resolved RCA incidents (> 90d) and audit logs (> 90d).

### 🔒 Enterprise Session Security & Native Autofill
* **100% Reliable Native Browser Password Autofill**: Refactored `LoginView.vue` with native HTML inputs, standard form headers (`method="post"`, `autocomplete="on"`), and an unnested visibility toggle, enabling 1-click login and credential saving across Chrome, Edge, Safari, Firefox, and password managers (Bitwarden, 1Password).
* **Sliding 2-Hour Inactivity Timeout**: Dashboard requests automatically slide session expiration forward, keeping active operators logged in while expiring idle sessions safely after 120 minutes.
* **Concurrent Device Quotas**: Token-based `jti` tracking limiting accounts to 2 active sessions via FIFO rotation.
* **IP-Scoped Lockouts**: Failed login attempts isolated by `f"{client_ip}:{username}"`, preventing shared corporate NAT or VPN lockouts.

### 📊 Observability, Logging & Lifecycle
* **150MB Auto-Rotating Logging Suite**: Dual output to systemd console and bounded rotating files (`/var/log/netmon/api.log`, `engine.log`, `error.log`).
* **Global Access & Latency Middleware**: FastAPI middleware recording client IP, path, status, and execution latency in milliseconds.
* **Bulletproof Lifecycle Scripts**:
  - `deploy/upgrade.sh`: In-place `/etc/netmon/config.toml` migrator, pre-upgrade database backup, and auto-start on boot enforcement (`systemctl enable netmon-api netmon-engine`).
  - `deploy/uninstall.sh`: Safe decommission utility with automated pre-removal database dumps.
* **Vulnerability Mitigation**: Upgraded build-time dependency `nanoid` to `3.3.18` via npm overrides.

---

## [Version 1.5 (Beta)]

### 📈 Adaptive Baselines & Statistical Anomaly Detection
* **TimescaleDB Continuous Aggregates**: Hourly statistical rollups (`node_historical_baselines`) across 168 weekly hourly bins ($7\text{ days} \times 24\text{ hours}$).
* **1D In-Memory Z-Score Cache**: Fast $O(1)$ RAM cache calculating dynamic latency thresholds ($Z = \frac{x - \mu}{\sigma} > 3.0$) to eliminate static alert fatigue.

### 🔍 Concurrent Diagnostics & Root Cause Analysis (RCA)
* **Asynchronous Drop Diagnostics**: Immediate traceroute execution triggered on the first failed ping sub-cycle via non-blocking `asyncio.Semaphore(5)` queues.
* **Differential RCA Engine**: Side-by-side comparison of live failure traces against last-known baseline routes, differentiating local L2 drops from upstream carrier/transit link failures.
* **Topological Alert Suppression (`INFERRED_DOWN`)**: If 100% of downstream children behind an intermediate transit router fail, LNMP marks the router `DOWN`, marks children `INFERRED_DOWN`, and suppresses cascading alert storms.
* **4-Tier Network Boundary Detection**: Pure-Python `/proc/net/route` and `/proc/net/arp` inspection with FHRP regex (HSRP, VRRP, GLBP) to detect gateway and L2 segment boundaries.

### 🔐 Governance & Reliability
* **Role-Based Access Control (RBAC)**: Distinct `ADMIN` and `OPERATOR` permission models.
* **Forced Initial Password Reset**: Enforces credential change upon first operator login.
* **Streaming CSV Export**: Server-side cursor streaming with CSV formula injection sanitization (`=`, `+`, `-`, `@`).
* **PostgreSQL Type Safety**: Explicit UUID casting (`CAST(:id AS uuid)`) across all queries.
* **Frontend UI Polish**: Migrated to Vue 3 (Vite) and PrimeVue (Aura Preset) with physics stabilization to prevent topology canvas shaking.

---

## [Version 1.0 (Baseline)]

### 📡 Core Telemetry & Polling Foundation
* **The 10-Ping Sub-Cycle**: Polling 10 ICMP packets spaced 6 seconds apart within every 60-second window aligned to minute boundaries.
* **Dual-State Engine**: Decoupled macro availability (`operational_state`: UP/DOWN) from minute-level packet health (`detailed_state`: UP, UP-UNSTABLE, DOWN-UNSTABLE, DOWN).
* **Flap Suppression ($N=3$)**: In-memory state machine requiring 3 consecutive cycles (180 seconds) before committing state transitions.
* **Honest SLA Metrics**: Lifespan alignment and server blackout neutralization ($D_{\text{sla}} = T_{\text{total}} - U$) to eliminate administrative downtime skew.
* **FastAPI Backend & Vue 3 Dashboard**: Basic REST endpoints and visual RTT telemetry charting.
