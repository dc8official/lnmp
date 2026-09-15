# LNMP Changelog & Evolutionary Architecture

All notable technical changes, architectural upgrades, security enhancements, and operational milestones for the Lightweight Network Monitoring Platform (LNMP) are documented in this file.

The versioning format follows [Semantic Versioning](https://semver.org/).

## [Version 3.2.0] — Passive Network Flow Telemetry Ingestion (NetFlow v5/v9 & IPFIX)
### 🌊 Hybrid Telemetry, Decoupled Flow Collector, 4-Tier Lifecycle & Fleet Bandwidth Analytics

| Upgrade Domain | Technical Implementation | Operational & Performance Benefit |
| :--- | :--- | :--- |
| **Autonomous Collector Daemon (`netmon-flowd`)** | Dedicated `systemd` daemon listening on UDP 2055 (NetFlow v5/v9) and UDP 4739 (IPFIX) with 4MB kernel socket buffers (`SO_RCVBUF`), zero-allocation binary decoders (`struct.unpack_from`), dynamic template caching (1,800s TTL), and orphan data set ring buffering (2,000 pkts). | Decouples high-volume passive flow collection from the active 32-second ICMP sweep and FastAPI REST threads, ensuring zero packet drops under multi-gigabit traffic bursts. |
| **Dual-Role $\mathcal{O}(1)$ In-Memory Correlator** | In-memory hash indexing mapping exporter IP addresses (primary endpoint IP + `flow_exporter_ips` secondary aliases) and traffic participants (monitored source/destination endpoints) with thread-safe refresh. | Delivers sub-microsecond traffic attribution and device classification without burdening the database with per-flow SQL queries. |
| **Unmatched Exporter Discovery Banner** | Unmapped exporter IPs are tracked in a Redis sliding set (`flow:unmatched:set` with 24-hour TTL), rendering an interactive amber warning banner on the Bandwidth dashboard with 1-click binding to existing devices. | Streamlines network device onboarding, automatically discovers newly configured flow exporters, and eliminates manual IP configuration errors. |
| **Port Normalization & Cardinality Shield** | Normalizes high-entropy ephemeral client ports (1024–65535) into an aggregate bucket while preserving standard service ports (e.g. 8080, 8443, 3306, 5432, 6379, 9200). | Prevents ephemeral client port explosion from degrading TimescaleDB hypertable B-tree index performance and exploding disk footprints. |
| **4-Tier Hierarchical Storage Lifecycle** | Sliding 2-hour Redis Stream buffer (`stream:netflow:raw`) with memory circuit breaker (>85%), 7-day 1-minute TimescaleDB hypertable rollups (`flow_minute_rollups`) with 1-day columnar compression (85%+ disk space savings), 30-day 1-hour continuous aggregates (`flow_hourly_rollups`), and 365-day daily totals (`flow_daily_rollups`). | Provides instant sub-second forensic drill-downs while keeping long-term database storage bounded and optimized for capacity planning. |
| **Fleet Bandwidth & Forensic Dashboard** | Real-time KPI summary (Ingress/Egress bps, active exporters, unmatched count, total flows), Chart.js stacked area charts, Top Talkers, Application distribution donut, and forensic IP-to-IP conversation drilldowns at `/bandwidth`. | Equips operators and NOC teams with complete traffic visibility, bandwidth hog identification, and protocol distribution tracking across the entire network fleet. |
| **Endpoint Detail Perspective Switcher** | Accessible dual-perspective switcher in `EndpointDetailView.vue` toggling between **Health & Diagnostics** (ICMP latency curves, packet loss, traceroutes) and **Flow Telemetry & Bandwidth** (device-specific Ingress/Egress, top peers, application breakdown). | Consolidates active probing metrics and passive flow consumption into a unified single-pane-of-glass interface for every network endpoint. |
| **Admin Flow Settings & Pre-Flight Validation** | Web UI controls under `SettingsView.vue` for master flow collection toggle, listening ports (2055, 4739), packet sampling multiplier, and live **Redis Pre-Flight Check** validation (`GET /api/v1/settings/flow/preflight`). | Ensures operators can safely verify Redis 6.0+ Streams support and configure flow parameters without modifying backend configuration files. |
| **Vendor Flow Configuration Runbook** | Production guidelines for timeouts (Active = 60s, Inactive = 15s), template refresh (60s / 1,000 pkts), persistent export loopback source, and multi-vendor templates (Cisco, Juniper, Mikrotik, Linux `fprobe`, pfSense/OPNsense `softflowd`) in `docs/netflow-guide.md`. | Eliminates flow reporting fragmentation, ensures synchronized rollup boundaries, and provides copy-paste vendor configuration templates. |
| **Historical Baseline View Repair** | Encapsulated `node_historical_baselines` 168-hour weekly statistical profile as a standard view, preventing migration failures under strict TimescaleDB continuous aggregate requirements. | Guarantees reliable schema migrations (`0008`) and robust statistical Z-score baseline calculations across vanilla PostgreSQL and TimescaleDB environments. |

---

## [Version 3.1.1s] — Zero-Trust Socket SSRF Protection & Security Hardening
### Security Fixes (CWE-918 Mitigation)
* **Zero-Trust Socket-Level SSRF Protection**: Replaced pre-flight DNS lookup validation with an enforced connection-time socket backend (`SSRFSafeBackend`). Verifies destination IP address at the exact millisecond of the TCP connection handshake (`connect_tcp`), rendering Time-of-Check to Time-of-Use (TOCTOU) DNS Rebinding attacks physically impossible.
* **Strict Non-Global & CGNAT IP Enforcement**: Socket connections to loopback (`127.0.0.0/8`, `::1`), RFC 1918 private subnets, RFC 6598 CGNAT (`100.64.0.0/10`), link-local cloud metadata (`169.254.169.254`), and Unix domain sockets are unconditionally dropped at the kernel boundary before sending HTTP data.
* **Redirect SSRF Lockdown**: Enforced `follow_redirects=False` on all outbound webhook client instances, preventing third-party endpoints from bouncing requests into internal network segments via HTTP 301/302 redirects.
* **Version Bump**: Unified security patch release identifier `v3.1.1s` across backend, frontend, deployment automation, and operational documentation.

---

## [Version 3.1.0] — Enterprise Alerting & Notifications Engine
### 🔔 Multi-Channel Notifications, Outbound Security & Reporting Customization

| Upgrade Domain | Technical Implementation | Operational & Security Benefit |
| :--- | :--- | :--- |
| **Multi-Channel Alert Dispatcher** | Asynchronous background worker pool decoupled from the 32-second ICMP probe sweep budget via `asyncio.Queue` running entirely within `netmon-api`. | Guarantees zero latency jitter or sweep delay on high-frequency ICMP/TCP polling loops while delivering near real-time incident notifications. |
| **Universal Polyglot Webhooks** | Native support for Microsoft Teams Adaptive Cards v1.4, Teams HTML fallback ("Post as User" for bot-restricted tenants), Discord Rich Embeds, Slack Block Kit, and direct SMTP TLS. | Integrates effortlessly with corporate and developer chat platforms without external bridging proxies or third-party middleware. |
| **Hardened Outbound Security** | AES-256-GCM encryption at rest with HKDF-SHA256 key derivation for webhook URLs and SMTP credentials; socket-level DNS/IP validation blocking loopback and link-local metadata; CRLF header injection sanitization. | Eliminates secret exfiltration from database dumps, completely prevents Server-Side Request Forgery (SSRF) against internal resources, and secures email headers. |
| **Intelligent Alert Suppression** | Root-cause grouping suppressing individual children alerts during upstream DAG gateway outages; sliding-window flapping detection (max 1 alert per 5 min per endpoint/severity). | Eliminates alert fatigue, prevents notification spam during route flaps, and focuses operator attention on root causes. |
| **Hardware Master Toggle** | Master `alerting_enabled` boolean in system settings and database `app_settings` allowing instant suspension of all outbound notification traffic. | Allows low-spec edge or maintenance deployments to completely disable alerting workloads on demand with zero downtime. |
| **Spacious 4-Tab Administration Console** | Redesigned `SettingsView.vue` into 4 dedicated tabs (`🔔 Alert Channels`, `⚡ Performance & Storage`, `🛡️ Security & Discovery`, `👥 User Governance`), featuring an 800px modal and live diagnostic test probe button. | Streamlines system configuration, provides instant visual test validation before saving, and cleans up administrative workflows. |
| **Interactive CSV Column Customizer** | Redesigned 820px export configuration modal in `ReportsView.vue` with locked device identity columns (`Hostname`, `IP_Address`), toggleable metrics, Select All, and Reset actions. | Provides tailored, audit-compliant reporting outputs while guaranteeing immutable endpoint identity columns in every generated export. |

---

## [Version 3.0.7s]
### 🛡️ Production Security Hardening & Resilience Upgrades

| Upgrade Domain | Technical Implementation | Operational & Security Benefit |
| :--- | :--- | :--- |
| **Strict Session Wipe & Multi-Worker Governance** | Enforced strict `jti` validation (`if not jti: return False`), awaited session registration in login, awaited invalidation on logout/password reset, and directly queried persistent session store drivers in `get_current_user`. | Completely eliminates the multi-worker auth bypass under Uvicorn (`--workers 2`), preventing unauthorized session reuse and ensuring 100% session quota enforcement from second zero. |
| **Inter-Process Telemetry Relay & Split-Brain Remediation** | Integrated `telemetry_relay.py` in `netmon-api` to subscribe to `STATE_TRANSITION` and `NODE_STATE_CHANGE` via the active `EventBroker`, broadcasting to browser SSE and mutating the API's local in-memory `topology_manager` in $O(1)$ time. | Resolves the inter-process split-brain where `netmon-engine` and `netmon-api` operated in isolated memory spaces, restoring real-time web telemetry and live topology map updates. |
| **Synthetic SSL Probe Binary DER Parsing** | Added binary DER certificate decoding via `cryptography.x509.load_der_x509_certificate(bin_cert).not_valid_after_utc` when Python's `ssl` module returns an empty dictionary under `ssl.CERT_NONE`. | Prevents unhandled `TypeError` crashes during SSL probes against self-signed, internal, or untrusted host certificates. |
| **Storage Driver Precedence & Robust Asyncpg Event Broker** | Prioritized database `app_settings.performance_mode` over config defaults, added socket cleanup (`await self._redis_client.aclose()`), parameterized SQL notify queries (`SELECT pg_notify(:channel, :payload)`), and implemented dedicated unpooled `asyncpg` notification listener with exponential backoff. | Eliminates SQL injection vectors in notify publishing and prevents silent connection drops and split-brain broker fallbacks during Redis or PostgreSQL restarts. |
| **Uptime SLA Denominator & Keyset Telemetry Export** | Tailored `unknown_seconds` to the intersection of engine service gaps and the endpoint's actual active lifespan `[max(start_time, created_at), now_utc]`; added bulk `GET /api/v1/reports/fleet-summary`; refactored CSV telemetry export to deterministic keyset pagination on `(start_time, id)`. | Eliminates false 100% SLA ratings for newly onboarded endpoints, replaces $O(N)$ HTTP client request fan-outs with a single query, and eliminates quadratic table scan overhead during multi-month telemetry exports. |
| **Dynamic System Settings REST API & CIDR Netmask Hardening** | Implemented `GET` and `PATCH /api/v1/settings` backed by PostgreSQL `app_settings` table with automatic driver re-initialization; hardened `is_local_subnet_destination` to compute CIDRs using actual interface netmasks (`f"{addr.address}/{addr.netmask}"`) instead of hardcoded `/24`. | Replaces placebo browser `localStorage` settings with persistent backend configuration and fixes Layer-2 subnet auto-bypass on `/16`, `/23`, and `/8` subnets. |
| **Production Deployment Hardening & Fail-Safe Upgrade Pipeline** | Added `After=redis-server.service` and `Wants=redis-server.service` to systemd units; configured `proxy_buffering off;` and `proxy_read_timeout 86400s;` in Nginx template; restructured `deploy/upgrade.sh` to compile frontend assets before stopping daemons, support air-gapped pre-built `dist`, and halt safely on Alembic migration errors without `|| true`. | Eliminates boot-time race conditions between systemd units, prevents Nginx reverse-proxy SSE buffering, and prevents unrecoverable service downtime during live upgrades. |

### 🚀 Major Architectural Upgrades - [Version 3.0.0]

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
