# lnmp — Network Telemetry & Monitoring Platform v1(beta)

A high-precision, decoupled network monitoring architecture designed for continuous ICMP telemetry collection, state verification, and historical logging. 

## Architectural Overview
The platform is explicitly decoupled into independent computing layers to ensure continuous telemetry gathering regardless of frontend user activity:
* **The Monitoring Engine:** A persistent Python background daemon running via systemd, synchronized directly to absolute minute clock boundaries.
* **The State Machine:** A localized verification engine that enforces a strict 3-cycle confirmation threshold to filter out transient network jitter.
* **The Telemetry Ledger:** A time-series database architecture leveraging PostgreSQL to record detailed per-minute success metrics and isolated average round-trip times (RTT).
* **The Service API:** A lightweight FastAPI routing framework that serves UTC-normalized ISO 8601 telemetry timelines.
* **The Interface UI:** A high-contrast, minimalist monochrome Vue.js dashboard built to optimize scannability and eliminate cognitive visual noise.

## Core Core Stack
* **Backend:** Python 3, Asyncio, FastAPI, SQLAlchemy
* **Database:** PostgreSQL (Time-Series Optimization)
* **Frontend:** Vue.js, Tailwind CSS
* **System Layer:** Linux systemd Daemon, Native Raw Sockets (CAP_NET_RAW)

## Getting Started
1. Clone the repository into your operational environment.
2. Configure the database credentials and domain bindings inside `/etc/netmon/netmon.env`.
3. Initialize the database schema migrations.
4. Enable and start the background service: `systemctl enable --now netmon-engine`.

## License & Authorship
Core Architecture designed and authored by Kenneth Nnorom.
This project is licensed under the terms of the Apache License 2.0. See the LICENSE file for full legal details.
