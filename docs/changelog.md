# LNMP Changelog & Evolutionary Architecture

All notable technical changes, architectural upgrades, security enhancements, and operational milestones for the Lightweight Network Monitoring Platform (LNMP) are documented in this file.

The versioning format follows [Semantic Versioning](https://semver.org/).

---

## [Version 3.0.0] — Current Production Release

### 🚀 Major Architectural Upgrades

| Upgrade Domain | Technical Implementation | Operational & Performance Benefit |
| :--- | :--- | :--- |
| **SQLAlchemy 2.0 ORM & Repository Layer** | Migrated all database operations from raw SQL string sprawl to pure typed async declarative models (`backend/app/models/`) and a clean Repository Layer (`backend/app/repositories/`). | Eliminates SQL injection vectors, god controllers, and coupling; standardizes database access with full IDE autocompletion and type-safety. |
| **SQL-Level Pagination** | Implemented `limit` and `offset` query parameters across repositories with metadata envelopes (`total_count`, `page`, `page_size`, `total_pages`). | Drastically reduces server memory consumption and DB serialization overhead when querying large endpoint and event lists. |
| **Pydantic-Settings Centralization** | Modernized configuration management with nested `Settings` models reading from `/etc/netmon/config.toml` and environment variables. | Clean validation of system configurations on startup with clear error messages for missing or invalid parameters. |
| **60s Cycle Timing Budget Refactor** | Re-tuned monitoring cycle from `10 pings @ 6.0s` to `5 pings @ 8.0s` with randomized startup jitter (0–2000ms offset). | Guarantees probe pass completion in ~32s, leaving a spacious **28-second headroom window** before the minute boundary to eliminate thundering herds and DB lock contention. |
| **Dynamic In-Memory Endpoint Registry** | Thread-safe, asyncio concurrent `EndpointRegistry` with sub-minute lifecycle synchronization (`add_endpoint`, `update_endpoint`, `remove_endpoint`). | Enables zero-downtime endpoint onboarding and configuration updates without requiring engine daemon restarts. |
| **High-Fidelity Route Diagnostics** | Upgraded traceroute parameters to `traceroute -n -q 2 -w 3 -m 30 -I` with robust multi-probe latency extraction and automatic Layer-2 subnet bypass. | Eliminates silent hop parsing dropouts, measures multi-probe transit variability, and avoids wasteful traceroutes on direct broadcast segments. |
| **Dual-Driver Storage Architecture** | Abstracted `SessionStore` (`PostgresSessionStore`, `RedisSessionStore`) and `EventBroker` (`PostgresEventBroker`, `RedisEventBroker`) managed via `StorageDriverManager`. | Enables high-performance Redis in-memory acceleration while retaining 100% functionality on standalone PostgreSQL deployments. |
| **Async Argon2id Password Hashing** | Wrapped CPU-intensive password hashing and verification in `asyncio.to_thread` with trusted CIDR IP sanitization. | Prevents event-loop stalls under concurrent authentication traffic and guarantees accurate audit logging behind reverse proxies. |
| **Real-Time Server-Sent Events (SSE)** | High-throughput streaming endpoint `GET /api/v1/events/stream` emitting `STATE_TRANSITION`, `NODE_STATE_CHANGE`, and `RCA_INCIDENT` envelopes with 15s heartbeat pings. | Eliminates periodic client polling, reducing backend HTTP request load while providing instantaneous sub-second UI updates. |
| **Multi-Protocol Synthetic Probes** | Lightweight async probes for TCP port reachability, HTTP/HTTPS status validation, and SSL/TLS certificate expiry with strict SSRF defense. | Extends platform monitoring beyond ICMP to application-layer service health and certificate expiration alerts. |
| **Frozen-Physics Topology Recolor** | Real-time Vis-Network node recoloring upon SSE `NODE_STATE_CHANGE` events with locked physics (`physics: { enabled: false }`). | Updates network status colors in real time without causing node jitter, layout recalculations, or canvas movement. |
| **Dashboard Layout Overhaul** | Added Global Network Health KPI strip with live filter pills, dual view switcher (Visual Card Grid vs Dense Table), and real-time SSE connection badge. | Gives operators instant fleet-wide SLA visibility and high-density sorting capabilities across thousands of monitored devices. |
| **Admin Settings Console** | Dedicated administrative interface (`/settings`) for storage driver switching, L2 auto-bypass toggles, security timeouts, and user governance. | Simplifies runtime system tuning and user administration into a centralized web UI. |
| **Design System & Accessibility Polish** | High-contrast monochrome theme, tabular monospace numbers (`font-variant-numeric: tabular-nums`), WCAG 2.1 AA focus rings, and `aria-live` screen reader regions. | Guarantees compliance with accessibility standards and ensures maximum legibility in mission-critical NOC environments. |

---

## [Version 2.0 (Beta)]

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
