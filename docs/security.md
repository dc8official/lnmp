# LNMP Security Model & Threat Hardening

This document outlines the security architecture, threat model, authentication mechanisms, and privilege boundaries enforced in LNMP v2.0 (Beta).

---

## 1. Network & Firewall Perimeter

| Component | Port | Binding | Security Policy |
| :--- | :--- | :--- | :--- |
| **Nginx Web Server** | `80` / `443` | `0.0.0.0` (Public) | Terminating SSL/TLS, enforcing secure HTTP headers, proxying to backend API. |
| **FastAPI Backend** | `8000` | `127.0.0.1` (Loopback Only) | Internal service; rejected from public internet access by default. |
| **PostgreSQL Database** | `5432` | `127.0.0.1` (Loopback Only) | Internal datastore; strictly password-protected and loopback-bound. |

---

## 2. Authentication & Session Security

### A. JWT in Secure HttpOnly Cookies
* **Protection Against XSS**: Authentication tokens are stored inside browser `HttpOnly` and `SameSite=Lax` cookies, preventing malicious JavaScript from reading session tokens.
* **Sliding 2-Hour Inactivity Window**: Active operator requests continuously slide the session expiration timestamp forward. Sessions idle for longer than 120 minutes expire automatically.

### B. Concurrent Device Quotas (Max 2 Active Sessions)
* **JWT `jti` Tracking**: Each login generates a cryptographically unique session ID (`jti`).
* **FIFO Eviction**: If an account logs in on a 3rd device, the system automatically invalidates the oldest session token without locking the user out.

### C. IP-Scoped Failed Login Lockouts
* **Brute-Force Shield**: 5 consecutive failed login attempts within 15 minutes trigger a 15-minute temporary lockout.
* **NAT / VPN Isolation**: Lockout states are keyed by `f"{client_ip}:{username}"`. If an external attacker attempts to brute force an administrator account, only the attacker's IP is blocked; legitimate admins at other locations remain completely unaffected.

---

## 3. Principle of Least Privilege & Linux Capabilities

* **Non-Root Execution**: The `netmon-api` and `netmon-engine` daemons run under an isolated system service user (`netmon`).
* **Capability Isolation (`CAP_NET_RAW`)**: Rather than granting full `root` privileges to Python or system binaries, only the specific network packet crafting capability (`CAP_NET_RAW`) is granted.

---

## 4. Input Sanitization & Attack Mitigations

### A. CSV Formula Injection Defense
* In telemetry exports, spreadsheet software (Excel, LibreOffice) can execute arbitrary code if cell values start with `=`, `+`, `-`, or `@`.
* **Sanitization**: All string exports are scrubbed with single-quote escaping (`'`) before streaming to prevent client-side spreadsheet execution.

### B. SQL Parameterization
* All database queries utilize SQLAlchemy parameter binding (`:endpoint_id`, `:ip_address`) or explicit type casting (`CAST(:id AS uuid)`), neutralizing SQL injection vectors.

### C. Role-Based Access Control (RBAC)
* **`ADMIN`**: Full permissions to create/delete endpoints, modify user accounts, reset passwords, and change system settings.
* **`OPERATOR`**: Read-only permissions to view telemetry graphs, inspect the topology canvas, and download CSV reports.
