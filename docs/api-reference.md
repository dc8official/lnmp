# LNMP API Reference

The LNMP (Network Monitoring Platform) v1.5 exposes a RESTful API built on FastAPI. The API is located under the `/api/v1` base path and requires JWT Bearer authentication for most endpoints.

## Base URL
`http(s)://<server-ip>:<port>/api/v1`

---

## 1. Authentication (`/auth`)

All routes (except `/login`) require a valid JWT passed in the Authorization header:
`Authorization: Bearer <your_jwt_token>`

### `POST /auth/login`
Authenticates a user and returns a JWT access token.
- **Request Body:** JSON containing `username` and `password`.
- **Response:** `200 OK` with JSON `{ "access_token": "...", "token_type": "bearer" }`

---

## 2. Endpoints Management (`/endpoints`)

Manage the network devices being monitored.

### `GET /endpoints`
Lists all monitored endpoints.
- **Query Params:** `site` (optional filter), `status` (optional filter).
- **Response:** `200 OK` with an array of endpoint objects.

### `POST /endpoints`
Onboards a new endpoint for monitoring.
- **Request Body:**
  ```json
  {
    "hostname": "Core-Router-NY",
    "ip_address": "10.0.0.1",
    "site": "New York",
    "allow_incident_trace": true,
    "allow_topology_discovery": true
  }
  ```
- **Response:** `201 Created`

### `GET /endpoints/{id}`
Retrieves detailed information, current status, and recent telemetry for a specific endpoint.

### `PUT /endpoints/{id}`
Updates configuration flags or properties for an endpoint.

### `DELETE /endpoints/{id}`
Removes an endpoint from monitoring and drops its historical telemetry.

---

## 3. Topology (`/topology`)

Interact with the Root Cause Analysis and adjacency mapping data.

### `GET /topology`
Retrieves the full L2/L3 parent-child adjacency map used by the frontend `vis-network` graph.
- **Response:** `200 OK` returning an object containing arrays of `nodes` and `edges`.

---

## 4. Reports & Telemetry (`/reports`)

Retrieve historical metrics and incident data.

### `GET /reports/telemetry/{endpoint_id}`
Retrieves time-series latency data.
- **Query Params:** `start_time` (ISO8601), `end_time` (ISO8601).
- **Response:** Array of telemetry data points (latency, jitter, packet loss).

### `GET /reports/incidents`
Lists historical incidents across the platform.
- **Query Params:** `severity` (optional), `limit` (default 100).
- **Response:** Array of incident objects including trigger times, resolution times, and captured Z-scores.

### `GET /reports/export/csv`
Streams a CSV file containing bulk telemetry data. Formulas (like `=SUM()`) are escaped server-side to prevent spreadsheet injection attacks.

---

## 5. Users (`/users`)

Manage operator and admin accounts. (Requires `Admin` role).

### `GET /users`
Lists all registered users.

### `POST /users`
Creates a new user account.
- **Request Body:** `username`, `password`, `role` ("Admin" or "Operator").

### `PUT /users/{id}/reset-password`
Forces a password reset for a specific user on their next login.

---

## HTTP Status Codes

- `200 OK` - Request succeeded.
- `201 Created` - Resource created successfully.
- `401 Unauthorized` - Missing or invalid JWT token. Session may be expired or user disabled.
- `403 Forbidden` - User lacks the required RBAC permissions (e.g., Operator trying to delete an endpoint).
- `404 Not Found` - Resource (Endpoint, User, etc.) does not exist.
- `422 Unprocessable Entity` - Payload validation error (handled automatically by FastAPI/Pydantic).
