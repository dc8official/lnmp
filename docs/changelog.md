# LNMP Changelog & Evolutionary Architecture

All notable technical changes, architectural upgrades, security enhancements, and operational milestones for the Lightweight Network Monitoring Platform (LNMP) are documented in this file.

The versioning format follows [Semantic Versioning](https://semver.org/).

---

## [Version 2.0 (Beta)] — Current Release

### ✨ Feature Updates

| Feature Module | Technical Mechanism | Operational Benefit |
| :--- | :--- | :--- |
| **Crossing-Free Topology Map** | BFS DAG Longest-Path Layering (`Level(v) = max(Level(u) + 1)`) + Sugiyama (1981) Barycenter Reduction | Assigns exact physical hop depth tiers to every node; consolidates shared routes and completely eliminates false diagonal wire crossings. |
| **Gansner Coordinate Alignment** | Gansner / DOT (1993) heuristic (`blockShifting: true`, `parentCentralization: true`) | Centers parent routers directly above child clusters and provides spatial corridor shifting between distinct subtrees to avoid branch overlap. |
| **Horizontal ⇄ Vertical Switcher** | Dynamic `layout.hierarchical.direction` (`LR` vs `UD`) toggle with directional tangent constraints | Allows operators to switch between top-to-bottom and widescreen left-to-right layouts with animated, smooth transitions. |
| **Native Browser Password Autofill** | Standard HTML `name`, `autocomplete`, and unnested native input architecture | Enables instant 1-click autofill and credential saving across Chrome, Edge, Safari, Firefox, and password managers (Bitwarden, 1Password). |
| **Sliding 2-Hour Inactivity Timeout** | Sliding window token and session cookie renewal on active HTTP requests | Prevents unexpected mid-task logouts for active operators while guaranteeing that idle sessions safely expire after 120 minutes. |
| **Token-Based Session Quotas** | JWT `jti` tracking with in-memory FIFO rotation (Max 2 concurrent sessions) | Prevents account sharing and stale logins while allowing seamless multi-device use without conflicting with colleagues behind shared NAT/VPN gateways. |
| **IP-Scoped Lockout Protection** | Failed login attempt tracker keyed by `f"{client_ip}:{username}"` | External bot scans or single-device typos only lock out their specific origin IP, leaving legitimate admins at other locations unaffected. |
| **TimescaleDB 7-Day Compression** | Columnar hypertable chunk compression via migration `0005_v2_0_timescale_stability.py` | Reduces database storage growth by 90%+ while keeping years of historical telemetry 100% queryable for charts and reports. |
| **Continuous Aggregate Policies** | Automated hourly background refresh with crash-recovery catch-up | Accelerates historical baseline queries, ensures continuous aggregation, and saves server RAM during live dashboard usage. |

### 🛡️ Quality, Stability & Security Updates

| Hardening Module | Technical Mechanism | Operational Benefit |
| :--- | :--- | :--- |
| **Top-of-Minute DB Write Semaphore** | `asyncio.Semaphore(15)` in monitoring engine | Eliminates top-of-the-minute PostgreSQL connection pool exhaustion and thundering herds when polling hundreds of endpoints. |
| **Database Pool Scaling** | Expanded pool settings (`pool_size=20, max_overflow=30`) in `database.py` | Guarantees high-throughput query handling during simultaneous multi-user dashboard sessions. |
| **150MB Auto-Rotating Logging Suite** | Python `RotatingFileHandler` with dual console and file outputs (`/var/log/netmon/`) | Full diagnostic transparency into API requests, engine cycles, and errors with a hard-capped 150MB maximum disk footprint. |
| **Global Access & Latency Middleware** | Asynchronous FastAPI middleware capturing client IP, path, status, and latency | Pinpoints slow queries and monitors real-time API performance on every endpoint. |
| **Security Diagnostic Warning Logs** | Explicit warning-level logging on 401 unauthenticated and 403 lockout events | Provides auditability for authentication failures and security investigations. |
| **Automated 90-Day Retention Purge** | Daily background maintenance task in `diagnostics.py` | Automatically purges resolved RCA incidents (> 90d) and audit logs (> 90d) to prevent unconstrained database growth. |
| **Smart In-Place Config Migrator** | Automated config updater in `deploy/upgrade.sh` | Seamlessly updates `/etc/netmon/config.toml` defaults (120m timeout, 2-session limit) without overwriting database passwords or secrets. |
| **Systemd Auto-Start Enforcement** | Automatic `.service` unit copy and `systemctl enable` in install and upgrade scripts | Guarantees that monitoring daemons automatically start on server reboot without manual operator intervention. |
| **Dedicated Decommission Utility** | Interactive `deploy/uninstall.sh` with safety confirmation and pre-removal SQL dump | Allows safe, complete removal of platform services and web routing with guaranteed zero accidental data loss. |
| **Build-Time Vulnerability Mitigation** | NPM `overrides` locking `nanoid` to `>= 3.3.18` | Eliminates an infinite loop Denial-of-Service (DoS) vulnerability in frontend build tooling. |
| **Clean UI Branding** | Removed placeholder shield and hexagon icons; updated version badge to `lnmp v2.0(beta)` | Provides a clean, distraction-free user interface and professional visual hierarchy. |

---

## [Version 1.5 (Beta)]

### ✨ Feature Updates

| Feature Module | Technical Mechanism | Operational Benefit |
| :--- | :--- | :--- |
| **Adaptive Statistical Baselines** | TimescaleDB continuous aggregates across 168 weekly hourly bins (7 days × 24 hours) | Automatically captures diurnal and weekend network traffic variations without manual threshold configuration. |
| **1D In-Memory Z-Score Baseline Cache** | Compact $O(1)$ RAM cache calculating dynamic bounds (`Z = (x - μ) / σ > 3.0`) | Eliminates static alert fatigue by triggering alarms only when latency statistically deviates from normal time-of-day baselines. |
| **Concurrent Background Diagnostics** | Non-blocking `asyncio.Semaphore(5)` queue triggered on first sub-cycle packet drop | Captures microsecond-level transit path snapshots before dynamic routing protocols (OSPF, BGP) can reconverge. |
| **Differential Root Cause Analysis (RCA)** | Automated side-by-side comparison of live failure traces against baseline snapshots | Instantly isolates whether an outage is caused by a local broadcast drop or an upstream carrier/transit link failure. |
| **In-Memory Directed Acyclic Graph (DAG)** | Sequential discovery pipeline with single-vertex Trie/Tree deduplication and orphan pruning | Builds an exact parent-child network topology map with zero duplicate transit nodes. |
| **Topological Alert Suppression** | Downstream dependency tracking marking children as `INFERRED_DOWN` | Silences cascading alert storms when an upstream aggregation router fails, highlighting the true root cause. |
| **4-Tier Network Boundary Detection** | Pure-Python `/proc/net/route` and `/proc/net/arp` inspection with FHRP regex (HSRP/VRRP/GLBP) | Automatically detects host interfaces, default gateways, and virtual redundancy protocol boundaries. |
| **Streaming Telemetry CSV Export** | Server-side database cursor streaming rows with formula sanitization (`=`, `+`, `-`, `@`) | Allows exporting millions of telemetry rows cleanly without server memory bloat or spreadsheet formula execution risks. |
| **Role-Based Access Control (RBAC)** | Distinct `ADMIN` and `OPERATOR` permission models with dedicated user management view | Restricts configuration changes to administrators while giving operators read-only dashboard and diagnostic access. |
| **Forced Initial Password Reset** | Database-enforced `must_change_password` flag verified upon authentication | Ensures temporary onboarding credentials cannot be reused indefinitely. |
| **Granular Endpoint Diagnostic Controls** | Flags: `allow_incident_trace`, `allow_topology_discovery`, `manual_parent_id` | Prevents CPU storms and control-plane traffic overload on sensitive low-bandwidth network hardware. |

### 🛡️ Quality, Stability & Security Updates

| Hardening Module | Technical Mechanism | Operational Benefit |
| :--- | :--- | :--- |
| **Upstream CVE Patches** | Patched dependencies (form-data CRLF, Vite NTFS traversal, Axios prototype pollution) | Secures the platform against known supply-chain vulnerabilities. |
| **PostgreSQL Explicit UUID Casting** | Enforced `CAST(:id AS uuid)` across all SQLAlchemy queries and models | Eliminates runtime database type-coercion and UUID lookup errors. |
| **Physics-Stabilized Topology Canvas** | Vis-Network physics freeze after 200 stabilization iterations | Eliminates continuous canvas shaking, bouncing, and CPU drain during live polling updates. |
| **Ephemeral JSONB Diagnostic Retention** | Dedicated JSONB table with automated 14-day background purge worker | Keeps high-frequency time-series hypertables fast and query-optimized while preserving diagnostic traces. |
| **Non-Blocking Endpoint Creation** | Async background discovery (`_bg_run_initial_discovery`) | Delivers sub-50ms API responses when adding new endpoints by offloading initial traceroutes to background tasks. |
| **Dedicated CLI Password Reset Tool** | Standalone Python/Shell recovery script (`deploy/reset-admin-password.sh`) | Provides safe out-of-band administrative password recovery from the server CLI. |

---

## [Version 1.0 (Baseline)]

### ✨ Feature Updates

| Feature Module | Technical Mechanism | Operational Benefit |
| :--- | :--- | :--- |
| **The 10-Ping Sub-Cycle Poller** | 10 ICMP packets spaced 6 seconds apart within every 60-second window | Provides high-density sampling aligned precisely to absolute minute boundaries. |
| **Dual-State Operational Engine** | Decoupled `operational_state` (macro availability) from `detailed_state` (minute-level health) | Separates transient packet drops from true production outage incidents. |
| **Honest SLA Mathematics** | Lifespan alignment and server blackout neutralization (`D_sla = T_total - U`) | Eliminates administrative downtime windows and prevents false SLA calculation penalties. |
| **RESTful Service API & Web Dashboard** | FastAPI backend with Vue 3 / Chart.js real-time telemetry charting | Delivers real-time network visibility and RTT latency visualization. |
| **Endpoint CRUD Management** | Relational data model for target IP addresses, hostnames, and site tags | Centralizes network endpoint inventory management. |

### 🛡️ Quality, Stability & Security Updates

| Hardening Module | Technical Mechanism | Operational Benefit |
| :--- | :--- | :--- |
| **In-Memory Flap Suppression (N=3)** | State machine requiring 3 consecutive cycles (180s) of sustained change | Prevents alert flapping and notification spam caused by momentary packet jitter. |
| **Raw Socket ICMP Polling** | Linux `CAP_NET_RAW` capability on binary execution | Achieves high-efficiency packet crafting without spawning resource-heavy external sub-processes. |
| **Asynchronous Engine Architecture** | Single-threaded Python `asyncio` event loop | Prevents OS thread exhaustion while concurrently monitoring multiple endpoints. |
| **Baseline PostgreSQL Migrations** | Initial Alembic migration framework and relational schemas | Establishes structured, version-controlled database schema management. |
