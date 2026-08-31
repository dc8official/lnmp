# LNMP API Reference — Version 3.0.0

The LNMP (Network Monitoring Platform) v3.0.0 exposes a RESTful and Server-Sent Events (SSE) API built on FastAPI. The API is located under the `/api/v1` base path and requires JWT Bearer authentication or HttpOnly session cookies for protected endpoints.

## Base URL
`http(s)://<server-ip>:<port>/api/v1`

---

## 1. System & Real-Time Events

### `GET /api/v1/version`
Returns the current platform version metadata.
- **Response:** `200 OK`
  ```json
  {
    "status": "ok",
    "version": "3.0.0"
  }
  ```

### `GET /api/v1/health`
Performs system health check (database connection, monitoring engine status).

### `GET /api/v1/events/stream`
Connects to the real-time Server-Sent Events (SSE) telemetry stream.
- **Headers:** `Accept: text/event-stream`
- **Response Headers:** `Content-Type: text/event-stream`, `Cache-Control: no-cache, no-transform`, `Connection: keep-alive`
- **Event Types Streamed:**
  - `CONNECTED`: Emitted immediately upon connection.
  - `STATE_TRANSITION`: Emitted on endpoint state changes (`UP`, `UP-UNSTABLE`, `DOWN-UNSTABLE`, `DOWN`).
  - `NODE_STATE_CHANGE`: Emitted for real-time topology canvas node recoloring.
  - `RCA_INCIDENT`: Emitted on root-cause analysis triggers and resolutions.
  - `: heartbeat\n\n`: Emitted every 15 seconds if idle to prevent proxy timeouts.

---

## 2. Authentication (`/auth`)

All routes (except `/login` and `/version`) require a valid session or JWT token:
`Authorization: Bearer <your_jwt_token>`

### `POST /auth/login`
Authenticates a user and returns an access token.
- **Request Body:** JSON containing `username` and `password`.
- **Response:** `200 OK` with JSON `{ "access_token": "...", "token_type": "bearer" }`

### `POST /auth/logout`
Terminates the active session and invalidates the session token in the active storage driver.

### `POST /auth/change-password`
Updates the authenticated user's password.

---

## 3. Endpoints Management (`/endpoints`)

### `GET /endpoints`
Lists all monitored endpoints with SQL-level pagination and filtering.
- **Query Params:**
  - `page` (int, default: 1): Page number.
  - `page_size` (int, default: 50): Number of items per page.
  - `status` (string, optional): Filter by state (`UP`, `UNSTABLE`, `DOWN`, `UNKNOWN`).
  - `site` (string, optional): Filter by location.
- **Response Envelope:**
  ```json
  {
    "items": [...],
    "total_count": 120,
    "page": 1,
    "page_size": 50,
    "total_pages": 3
  }
  ```

### `POST /endpoints`
Onboards a new endpoint for monitoring with optional synthetic probe configuration.
- **Request Body:**
  ```json
  {
    "hostname": "Web-App-Gateway",
    "ip_address": "192.168.10.1",
    "device_type": "ROUTER",
    "location": "Main Datacenter",
    "is_l2_segment": false,
    "allow_topology_discovery": true,
    "probe_type": "HTTP_STATUS",
    "probe_port": 443,
    "probe_url": "https://service.internal/health",
    "probe_expected_status": 200
  }
  ```

### `GET /endpoints/{id}`
Retrieves detailed information, status, and baseline metrics for a specific endpoint.

### `PATCH /endpoints/{id}`
Updates configuration flags or properties for an endpoint. Synchronizes changes directly with the in-memory `EndpointRegistry`.

### `DELETE /endpoints/{id}`
Removes an endpoint from monitoring and deregisters it from the polling engine.

---

## 4. Topology & RCA (`/topology`)

### `GET /topology`
Retrieves the complete L2/L3 parent-child adjacency DAG map computed with Sugiyama barycenter crossing reduction.
- **Response:** `200 OK` returning an object containing arrays of `nodes` and `edges`.

---

## 5. Reports & Telemetry (`/reports`)

### `GET /reports/uptime/{endpoint_id}`
Retrieves SLA uptime availability percentage and state distribution metrics.
- **Query Params:** `start_date`, `end_date`.

### `GET /reports/events/{endpoint_id}`
Retrieves paginated historical state transition events.
- **Query Params:** `start_date`, `end_date`, `page`, `page_size`.

### `GET /reports/rtt-trend/{endpoint_id}`
Retrieves time-series latency curves against historical continuous aggregate baselines.

### `GET /reports/timeline/{endpoint_id}`
Retrieves state transition timeline entries.

### `GET /reports/audit-logs`
Retrieves paginated administrative audit logs (requires `Admin` role).

### `POST /reports/telemetry/export-batch`
Streams a sanitised CSV containing bulk telemetry data across multiple endpoints.

---

## 6. User Governance (`/users`)

Manage user accounts (requires `Admin` role).

### `GET /users/`
Lists all user accounts.

### `POST /users/`
Creates a new operator or administrator account.

### `POST /users/{id}/reset-password`
Forces a password reset for a specific user.

### `PATCH /users/{id}`
Updates a user account role (`ADMIN` / `VIEWER`) or active status.

### `DELETE /users/{id}`
Deactivates or deletes a user account.
