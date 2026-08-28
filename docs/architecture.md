# LNMP Architecture Overview — Version 2.0 (Beta)

The Network Monitoring Platform (LNMP) v2.0 (Beta) is designed with a decoupled, modular architecture to guarantee continuous telemetry collection, crossing-free topology visualization, resilient 24/7 database operations, and zero-downtime upgrades.

---

## Core Components

### 1. Monitoring Engine (The Poller)
* **Concurrency Model:** Uses native Python `asyncio` to perform high-density ICMP telemetry scans.
* **Precision & Protection:** Execution is aligned precisely to absolute minute boundaries. Database writes are protected by an `asyncio.Semaphore(15)` to eliminate top-of-minute connection pool exhaustion.

### 2. Hybrid Adaptive Alert Engine (Baseline & Z-Score)
* **In-Memory State Machine:** Suppresses transient jitter and minor anomalies to prevent alert fatigue.
* **Statistical Baselines:** Evaluates live latency against historical time-series bounds via Z-Score ($Z = \frac{x - \mu}{\sigma}$). Alerts are triggered only when $Z > 3.0$, indicating a true statistical deviation.

### 3. Diagnostic & Traceroute Subsystem
* **Trigger:** Initiated on the first detected drop sub-cycle of any endpoint.
* **Concurrency:** Operates asynchronously via an `asyncio.Semaphore` queue, capturing the path state at the exact moment of failure.

### 4. Topology & Root Cause Analysis (RCA) Engine
* **Discovery Pipeline:** Runs sequentially during device onboarding and scheduled midnight passes.
* **Topological Inference:** If a transit router fails, 100% of downstream children become unreachable. The RCA engine marks the transit node `DOWN`, marks dependent children `INFERRED_DOWN`, and suppresses downstream alert storms.

### 5. Interactive Crossing-Free Topology Map
* **4-Phase Sugiyama & Gansner Framework**:
  1. **Phase 1: BFS DAG Longest-Path Layering ($L(v) = \max(L(u) + 1)$)**: Assigns every node to its exact discrete traceroute hop depth, consolidating shared gateways and eliminating backward/diagonal cross-tier links.
  2. **Phase 2: Crossing Reduction (`edgeMinimization: true`)**: Sugiyama barycenter reordering of sibling nodes on each level to ensure parallel, non-overlapping downward edge channels.
  3. **Phase 3: Coordinate Assignment (`blockShifting: true`, `parentCentralization: true`)**: Gansner subtree separation to prevent branch collision and center routers directly over downstream child clusters.
  4. **Phase 4: Directional Spline Routing (`cubicBezier`)**: Dynamic tangent constraint channeling aligned with the active layout orientation.
* **Layout Switcher:** Dynamic **Horizontal (Left-to-Right `LR`) ⇄ Vertical (Top-to-Bottom `UD`)** orientation with animated canvas transitions.

### 6. Telemetry Datastore & TimescaleDB Optimization
* **7-Day Chunk Compression:** Native TimescaleDB hypertable compression on `endpoint_events` older than 7 days, reducing disk storage by 90%+ while keeping all historical data 100% queryable.
* **Continuous Aggregate Policies:** Hourly background refresh on `node_historical_baselines` with automatic crash catch-up on server reboot.
* **Automated Retention Purging:** Daily background cleanup task purges resolved RCA incidents and audit logs older than 90 days.

### 7. Security, Auth & Logging Infrastructure
* **Sliding 2-Hour Sessions:** Active dashboard usage continuously slides session expiration forward.
* **Token-Based Concurrent Limits:** Limits user accounts to 2 active sessions (FIFO rotation) via JWT `jti` tracking.
* **IP-Scoped Lockouts:** Failed attempts isolated by `client_ip:username` to prevent shared NAT lockouts.
* **150MB Auto-Rotating Logs:** Dual output to systemd console and bounded rotating files (`api.log`, `engine.log`, `error.log`).

---

## Architectural Diagram

```mermaid
graph TD
    subgraph UI & API Layer
    A["Vue 3 Dashboard (Vite / PrimeVue)"] -->|REST / JSON / JWT Cookie| B["FastAPI Service API (v2.0)"]
    A -->|Sugiyama Graph Layout| T["Interactive Topology Map (LR / UD)"]
    end

    subgraph Security & Logging
    B --> M["Access & Latency Middleware"]
    M --> L["150MB Rotating Log Handlers (/var/log/netmon/)"]
    B --> S["Sliding Session & IP Lockout Manager"]
    end

    subgraph Core Engines
    B --> C{PostgreSQL 14+ / TimescaleDB}
    D["Monitoring Engine (asyncio)"] -->|Write Semaphore (15)| C
    E["Adaptive Baseline Engine"] <-->|Z-Score Baselines| C
    F["Diagnostic Subsystem"] -->|Async Traceroutes| C
    G["RCA Topology Engine"] <-->|Parent-Child Inference| C
    end

    subgraph Optimized Storage
    C --> H[("TimescaleDB Hypertables (7-Day Compression)")]
    C --> K[("Continuous Aggregates (Hourly Refresh)")]
    C --> I[("JSONB Diagnostic Traces (14-Day Retention)")]
    C --> J[("Audit Logs & RCA Incidents (90-Day Retention)")]
    end
    
    D -.->|Triggers on Drop| F
    F -.->|Informs| G
```
