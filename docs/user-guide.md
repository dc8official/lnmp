# LNMP User & Operator Guide — Version 3.0.0

Welcome to the LNMP Network Monitoring Platform v3.0.0 user guide. This document explains how to navigate the web dashboard, use the interactive topology visualizer, interpret multi-protocol probes, and manage system settings.

---

## 1. Authentication & Session Security

LNMP v3.0.0 provides enterprise-grade session protection:
* **Browser Password Autofill:** The login page supports native browser credential managers (Chrome, Edge, Safari, Firefox, Bitwarden, 1Password) for 1-click authentication.
* **Sliding 2-Hour Inactivity Timeout:** Sessions slide forward on active requests. If idle for 120 minutes, sessions expire automatically.
* **Concurrent Device Quotas:** Accounts are allowed up to 2 active sessions (managed via FIFO rotation).
* **IP-Scoped Lockouts:** Brute-force protection isolates failed attempts by `<Client_IP>:<Username>`, ensuring legitimate users on other networks are never locked out.
* **Forced Initial Password Reset:** First-time logins require setting a secure replacement password before platform access is granted.

---

## 2. Real-Time Dashboard Overview (`/`)

The v3.0.0 dashboard provides instantaneous fleet telemetry:

### Global Network Health KPI Strip
* **Summary Ribbon:** Displays total monitored devices, count of `🟢 UP`, `🟡 UNSTABLE`, `🔴 DOWN` devices, and the aggregate **Fleet SLA %**.
* **Interactive Filter Pills:** Clicking any state card (e.g. `🔴 DOWN`) instantly filters the endpoint list without triggering a page reload.

### Dual View Switcher
* **Visual Card Grid:** Rich visual cards showcasing live status badges, latency indicators, packet loss bars, and quick diagnostic links.
* **Dense Sortable Data Table:** High-density tabular view displaying Hostname, IP, Detailed Operational State, Average Latency, Packet Loss %, and 30-Day SLA Uptime %. Columns are sortable for rapid fleet triage.

### Real-Time Telemetry Stream
* Connected directly to Server-Sent Events (SSE). An indicator badge in the top right confirms connection status (`🟢 Live SSE` / `🟡 Reconnecting...`).

---

## 3. Interactive Topology Map (`/topology`)

Visualizes the parent-child network hierarchy with crossing-free routing:

### Features & Controls
* **Layout Switcher:** Toggle between **Vertical View (Top-to-Bottom)** and **Horizontal View (Left-to-Right)**.
* **Frozen-Physics Real-Time Recoloring:** State changes update node colors in real time via SSE without recalculating coordinates or causing canvas movement.
* **Dynamic Legend Badges:** Glowing count badges in the legend show live counts of Root, UP, UNSTABLE, DOWN, and Transit nodes.
* **Topological Root Cause Analysis (RCA):**
  - When an upstream transit gateway fails, dependent nodes are automatically classified as `INFERRED_DOWN`, preventing alert fatigue.

---

## 4. Endpoint Details & Synthetic Probes (`/endpoints/:id`)

Clicking any endpoint opens its diagnostic view:
* **24-Hour Telemetry Graphs:** Interactive latency and packet loss curves with TimescaleDB continuous aggregate baselines.
* **Multi-Protocol Synthetic Metrics:** View TCP connect latency, HTTP response codes, and SSL certificate expiration remaining days.
* **High-Fidelity Traceroutes:** View hop-by-hop latency breakdowns and identify failure transit boundaries.

---

## 5. Admin Settings Panel (`/settings`)

Administrators can tune platform behavior in real time:
* **Performance & Storage Engine:** Toggle between **Standard Mode (PostgreSQL-Native)** and **Memory Acceleration Mode (Redis)**.
* **Network Discovery:** Enable or disable Layer-2 Subnet Auto-Bypass.
* **Security Policies:** Adjust session inactivity timeout (15m – 24h) and brute-force lockout thresholds.
* **User Governance:** Create, update, or deactivate operator and administrator accounts and issue temporary password resets.
