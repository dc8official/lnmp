# noop — Network Monitoring Platform

A lightweight, event-driven network uptime monitoring platform.

## Stack
- Backend: FastAPI (Python 3.11+)
- Monitoring Engine: Python asyncio
- Database: TimescaleDB (PostgreSQL)
- Frontend: Vue.js + PrimeVue
- Deployment: Nginx + systemd on Debian 12+ / Ubuntu 22.04+

## Structure
- `backend/` — FastAPI application and database layer
- `monitoring/` — Asyncio monitoring engine
- `frontend/` — Vue.js reporting interface
- `deploy/` — Installation, configuration, and service files
- `tests/` — Backend and monitoring unit tests

## Setup
See deploy/INSTALL.md for full installation instructions.
