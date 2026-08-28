# LNMP User & Operator Guide — Version 2.0 (Beta)

Welcome to the LNMP Network Monitoring Platform user guide. This document explains how to navigate the web dashboard, use the interactive topology visualizer, and manage monitored endpoints.

---

## 1. Authentication & Security

LNMP employs enterprise-grade session and authentication security:
* **Browser Password Autofill:** The login page supports native browser credential managers (Chrome, Edge, Safari, Firefox, Bitwarden) for instant 1-click login and secure credential saving.
* **Sliding 2-Hour Session Inactivity:** Active operators will never be interrupted while working. As long as you interact with the dashboard, your session slides forward. If idle for 2 hours, the session expires safely.
* **Concurrent Device Quotas:** Accounts are allowed up to 2 active sessions. Logging in on a 3rd device automatically evicts your oldest session without locking you out.
* **IP-Scoped Lockouts:** If an attacker or wrong password is submitted 5 times from one IP, only that IP is locked out for 15 minutes. Legitimate operators at other locations remain unaffected.
* **Forced Initial Password Reset:** New users must update their temporary password on first login.

---

## 2. Dashboard Overview (`/`)

The main dashboard provides a real-time overview of the monitored network:
* **Global Health Metrics:** Displays active endpoints, uptime percentages, and active incidents.
* **Telemetry Charts:** RTT latency curves plotted against dynamic historical baselines (`Z > 3.0` triggers).
* **Active Incidents Table:** Sorted list of all currently failing or anomalous endpoints with direct links to root-cause diagnostics.

---

## 3. Interactive Topology Map (`/topology`)

The topology map visualizes the network hierarchy and root cause dependencies:

* **Horizontal (LR) ⇄ Vertical (UD) Layout Switcher:** Use the toolbar button to toggle between:
  - **Vertical View (Top-to-Bottom):** Root engine at the top, transit routers in the middle, endpoints at the bottom.
  - **Horizontal View (Left-to-Right):** Wide-screen layout flowing from left to right.
* **Crossing-Free Edge Routing:** Built with **BFS DAG Hop Layering**, Sugiyama barycenter reduction, and Gansner block shifting, automatically organizing devices into discrete hop tiers and eliminating tangled, overlapping link wires.
* **Node Categories & States:**
  - 🟦 **Square (Blue):** LNMP Engine (Root)
  - 🟩 **Circle (Green):** Monitored Endpoint `UP`
  - 🟧 **Circle (Amber):** Monitored Endpoint `UNSTABLE`
  - 🟥 **Circle (Red):** Monitored Endpoint `DOWN`
  - ⬡ **Hexagon (Grey):** Transit Router `UP`
  - ⬡ **Hexagon (Orange/Red):** Transit Router `FAILURE_POINT` (Root Cause)
  - ⬡ **Hexagon (Dark Red):** Transit Router `INFERRED_DOWN`
  - 🏷️ **Pill (Blue):** `[L2 Segment]` Layer 2 Broadcast Segment

---

## 4. Endpoint Details & Root Cause Diagnostics (`/endpoints/:id`)

Clicking any endpoint opens its comprehensive diagnostic drawer:
* **24-Hour Telemetry Graphs:** Interactive latency and packet loss curves with TimescaleDB continuous aggregate baselines.
* **Automated Failure Traceroutes:** View hop-by-hop JSON snapshots captured at the exact moment of failure.
* **Root Cause Analysis (RCA):** Differentiates local interface failures from upstream transit backbone failures.
