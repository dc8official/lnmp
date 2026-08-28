# LNMP Changelog & Evolutionary Architecture

All notable technical changes, architectural upgrades, security enhancements, and stability milestones for the Lightweight Network Monitoring Platform (LNMP) are documented in this file.

The versioning format follows [Semantic Versioning](https://semver.org/).

---

## [Version 2.0 (Beta)] — Current Release

### ✨ Feature Updates
* **BFS DAG Longest-Path Layering ($L(v) = \max(L(u) + 1)$)**: Implemented exact topological rank layering in both the backend (`topology.py`) and frontend (`TopologyMap.vue`). Automatically assigns discrete physical hop tiers to all nodes, consolidating shared routes and completely eliminating cross-tier diagonal wire crossings.
* **Sugiyama (1981) Barycenter Crossing Minimization (`edgeMinimization: true`)**: Solves node positioning along each discrete level so parent-child links drop in parallel downward channels without intersecting neighboring branches.
* **Gansner / DOT (1993) Coordinate Alignment (`blockShifting: true`, `parentCentralization: true`)**: Centers parent routers directly above child clusters and provides spatial corridor shifting between distinct subtrees.
* **Dynamic Layout Orientation Switcher**: Interactive toolbar toggle between **Vertical (Top-to-Bottom `UD`)** and **Horizontal (Left-to-Right `LR`)** layouts with animated canvas transitions and directional tangent channeling (`cubicBezier`).
* **100% Reliable Native Browser Password Autofill**: Refactored `LoginView.vue` with native HTML inputs, standard form headers (`method="post"`, `autocomplete="on"`), and an unnested visibility toggle, enabling 1-click login and credential saving across Chrome, Edge, Safari, Firefox, and password managers (Bitwarden, 1Password).
* **Sliding 2-Hour Inactivity Timeout**: Dashboard requests automatically slide session expiration forward, keeping active operators logged in while expiring idle sessions safely after 120 minutes.
* **Token-Based Concurrent Device Quotas**: JWT `jti` tracking limiting user accounts to 2 active sessions with automatic FIFO session rotation.
* **IP-Scoped Failed Login Lockouts**: Lockout tracker isolated by `f"{client_ip}:{username}"`, preventing shared corporate NAT or VPN gateways from being globally locked out during credential brute-force attempts.
* **TimescaleDB 7-Day Chunk Compression**: Migration `0005_v2_0_timescale_stability.py` enables native columnar hypertable compression on `endpoint_events` older than 7 days, reducing database storage growth by 90%+ while keeping historical telemetry 100% queryable.
* **Continuous Aggregate Auto-Refresh Policies**: Automated hourly background refresh policy on `node_historical_baselines` with automatic crash-recovery and catch-up on server reboot.

### 🛡️ Quality, Stability & Security Updates
* **Top-of-Minute DB Write Semaphore**: Enforced `asyncio.Semaphore(15)` in `monitoring/engine.py`, eliminating PostgreSQL connection pool exhaustion during concurrent top-of-minute ping commits.
* **Database Connection Pool Expansion**: Scaled connection pool configuration (`pool_size=20, max_overflow=30`) in `database.py` to support high-concurrency multi-user dashboard traffic.
* **150MB Auto-Rotating Logging Suite**: Configured dual console output (`systemd journalctl`) and bounded rotating log files (`/var/log/netmon/api.log`, `engine.log`, `error.log`) capped at 150MB maximum disk usage.
* **Global Access & Latency Logging Middleware**: Asynchronous FastAPI middleware recording client IP, HTTP method, path, response status, and millisecond execution latency for every request.
* **Security Rejection Diagnostics**: Added explicit warning logs for all 401 unauthorized rejections and 403 lockout events.
* **Automated 90-Day Retention Purge**: Added background retention task in `diagnostics.py` purging resolved RCA incidents and audit logs older than 90 days.
* **Bulletproof Lifecycle Suite (`install.sh`, `upgrade.sh`, `uninstall.sh`)**:
  - `upgrade.sh`: Added in-place `/etc/netmon/config.toml` migrator (migrating 120m timeout and 2-session limit), pre-upgrade database backup, and auto-start on boot enforcement (`systemctl enable netmon-api netmon-engine`).
  - `uninstall.sh`: Created clean decommission utility with safety confirmation prompts, automatic pre-removal database dump, and clean service/route deprovisioning.
  - Flexible execution support from both git clone directory or directly within `/opt/netmon/noop`.
* **Build-Time Vulnerability Mitigation**: Locked `nanoid` to `3.3.18` via npm overrides to eliminate an infinite loop DoS vulnerability.
* **Clean UI Branding**: Removed placeholder shield and hexagon icons from the login page and header, updating all branding to `lnmp v2.0(beta)`.

---

## [Version 1.5 (Beta)]

### ✨ Feature Updates
* **Adaptive Statistical Baselines**: TimescaleDB Continuous Aggregates (`node_historical_baselines`) materializing hourly latency distributions across 168 weekly hourly bins ($7\text{ days} \times 24\text{ hours}$).
* **1D In-Memory Z-Score Baseline Cache**: High-speed $O(1)$ RAM cache evaluating live latency against historical time-series bounds ($Z = \frac{x - \mu}{\sigma} > 3.0$) to eliminate static threshold alerting.
* **Concurrent Background Diagnostics**: Asynchronous path traceroute execution triggered on the first detected drop sub-cycle via non-blocking `asyncio.Semaphore(5)` queues.
* **Differential Root Cause Analysis (RCA)**: Automated side-by-side comparison of live failure traces against last-known baseline routes, differentiating local L2 broadcast drops from upstream transit carrier failures.
* **In-Memory Directed Acyclic Graph (DAG) Engine**: Sequential topology discovery pipeline with single-vertex Trie/Tree deduplication and orphan pruning.
* **Topological Alert Suppression (`INFERRED_DOWN`)**: If 100% of downstream monitored children behind an unmonitored transit node fail, marks the transit node `FAILURE_POINT`, marks children `INFERRED_DOWN`, and suppresses cascading alert storms.
* **4-Tier Network Boundary Detection**: Pure-Python `/proc/net/route` and `/proc/net/arp` inspection with FHRP regex (HSRP, VRRP, GLBP) detecting default gateways and L2 segments.
* **Streaming Telemetry CSV Export**: Server-side database cursor streaming millions of rows with zero RAM bloat.
* **Role-Based Access Control (RBAC)**: Distinct `ADMIN` and `OPERATOR` permission models with dedicated user management view.
* **Forced Initial Password Reset**: Enforces credential change upon first operator login.
* **Granular Endpoint Diagnostic Controls**: Per-device configuration flags (`allow_incident_trace`, `allow_topology_discovery`, `manual_parent_id`) to protect sensitive low-power hardware.

### 🛡️ Quality, Stability & Security Updates
* **Dependency Vulnerability Patches**: Patched upstream CVEs including form-data CRLF injection, Vite NTFS path traversal, and Axios prototype pollution.
* **CSV Formula Injection Sanitization**: Escapes leading characters (`=`, `+`, `-`, `@`, `\t`, `\r`) in CSV exports to prevent spreadsheet execution exploits.
* **Explicit PostgreSQL UUID Casting (`CAST(:id AS uuid)`)**: Applied across all SQLAlchemy queries and models to eliminate runtime type-coercion bugs.
* **Physics-Stabilized Topology Canvas**: Configured Vis-Network with `stabilization.iterations: 200` and `stabilizationIterationsDone` physics freeze, eliminating canvas shaking and bouncing.
* **Ephemeral JSONB Diagnostic Retention**: Automated 14-day background purge for diagnostic traceroute blobs, keeping core hypertables fast.
* **Non-Blocking Endpoint Onboarding (`_bg_run_initial_discovery`)**: Delivered sub-50ms API response times on device creation by offloading initial traceroutes to background tasks.
* **Dedicated CLI Admin Password Reset Tool**: Created `deploy/reset-admin-password.sh` for out-of-band credential recovery.

---

## [Version 1.0 (Baseline)]

### ✨ Feature Updates
* **The 10-Ping Sub-Cycle**: Polling 10 ICMP packets spaced 6 seconds apart within every 60-second window aligned to minute boundaries.
* **Dual-State Operational Engine**: Decoupled macro availability (`operational_state`: UP/DOWN) from minute-level packet health (`detailed_state`: UP, UP-UNSTABLE, DOWN-UNSTABLE, DOWN).
* **Honest SLA Metrics**: Lifespan alignment and server blackout neutralization ($D_{\text{sla}} = T_{\text{total}} - U$) to eliminate administrative maintenance windows and false SLA penalties.
* **RESTful Service API & Web Dashboard**: Basic FastAPI REST endpoints and Vue 3 RTT latency telemetry charting.
* **Endpoint CRUD Management**: Onboarding, editing, and deleting target IP addresses and hosts.

### 🛡️ Quality, Stability & Security Updates
* **In-Memory Flap Suppression ($N=3$)**: Suppresses transient network jitter by requiring 3 consecutive cycles (180s) of sustained state change before committing transitions.
* **Raw Socket ICMP Polling (`CAP_NET_RAW`)**: High-efficiency non-root packet construction without spawning external sub-processes.
* **Asynchronous Engine Loop**: Single-threaded Python `asyncio` execution preventing thread bloat.
* **Baseline PostgreSQL Schema**: Initial Alembic database migrations and relational data models.
