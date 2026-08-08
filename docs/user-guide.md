# LNMP User & Operator Guide

Welcome to the LNMP Network Monitoring Platform user guide. This document explains how to navigate the web dashboard, interpret alerts, and manage monitored endpoints.

## 1. Authentication & RBAC (Role-Based Access Control)

LNMP employs strict security and RBAC. To access the platform:
- Navigate to the login page (`/login`) and enter your credentials.
- Note: New operators are forced to reset their passwords upon their first login.
- **Roles:**
  - `Admin`: Can add/remove endpoints, manage users, and configure global settings.
  - `Operator`: Read-only access to dashboards, topology, and diagnostics.

## 2. Dashboard Overview (`/dashboard`)

The main dashboard provides a high-level overview of the entire monitored network.

- **Global Health Metrics:** Displays the total number of endpoints, active incidents, and global uptime percentage.
- **Topology Map:** An interactive, physics-based (`vis-network`) map showing the parent-child relationships of all devices. 
  - **Color Coding:** Green (Healthy), Red (Down/Incident), Orange (Inferred Down/Transit issue).
  - **Interaction:** You can drag nodes to rearrange the map. The physics stabilization engine prevents the nodes from continuously bouncing.
- **Active Incidents Table:** A real-time list of all currently failing or anomalous endpoints, sorted by severity and duration.

## 3. Endpoint Management (`/endpoints`)

This view allows administrators to onboard, edit, and delete monitoring targets.

### Adding an Endpoint
When adding a new device to be monitored, you provide:
- **Hostname/Alias:** A friendly name (e.g., `Core-Switch-01`).
- **IP Address:** The IPv4/IPv6 address to poll.
- **Site/Location Tag:** For grouping endpoints.
- **Configuration Flags:**
  - `Allow Incident Trace:` Enables or disables automated background traceroutes when this endpoint fails. Disable this for sensitive or low-CPU devices.
  - `Allow Topology Discovery:` Enables the automated L2/L3 boundary detection for this device.
  - `Manual Parent ID:` Overrides automatic topology discovery, forcing this endpoint to be a child of another specific endpoint.

## 4. Endpoint Details & Diagnostics (`/endpoint/:id`)

Clicking on any endpoint opens its detailed telemetry and diagnostic view.

### Real-Time Telemetry Chart
- Uses Chart.js to plot latency over the last 24 hours.
- **Baselines & Z-Scores:** The chart may show dynamic baselines (the expected "normal" latency for this specific time of day). If the live latency exceeds the dynamic baseline significantly ($Z > 3.0$), an alert incident is recorded.

### Incident History
A historical log of every time the endpoint went down or experienced severe latency jitter. 

### Diagnostic Traceroutes
If `Allow Incident Trace` is enabled on the endpoint, any incident will automatically trigger a path trace. You can view the full JSON traceroute payload captured at the exact moment of failure, allowing you to see exactly which hop in the transit path dropped the packets.

## 5. Interpreting Topology RCA (Root Cause Analysis)

One of LNMP's strongest features is RCA. If a core router goes offline, the 50 switches behind it will also become unreachable. 
Instead of sending you 51 alerts, LNMP's RCA Engine does the following:
1. Detects that the core router is down.
2. Marks the core router with a `DOWN` state.
3. Automatically marks the 50 dependent switches with an `INFERRED_DOWN` state.
4. Suppresses alerts for the `INFERRED_DOWN` devices, generating only one actionable alert for the core router.
