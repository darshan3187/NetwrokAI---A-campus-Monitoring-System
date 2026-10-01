# 06 — Database and REST API Reference

This document provides a comprehensive technical reference for NetworkAI's SQLite database schema, data retention policies, and all verified FastAPI REST endpoints.

---

## 1. Database Schema Reference

NetworkAI uses **SQLite 3** operating in **Write-Ahead Logging (WAL) mode** with foreign key constraints enabled via SQLAlchemy 2.0.

### 1.1 Table: `devices`
* **Purpose:** Central registry of campus network hardware infrastructure.
* **Columns:**
  * `id` (`VARCHAR(64)`, Primary Key, Indexed): System-unique identifier (e.g., `demo-core-01`, `sw-science-02`).
  * `name` (`VARCHAR(100)`, Not Null, Indexed): Human-readable device hostname.
  * `ip_address` (`VARCHAR(45)`, Not Null, Unique, Indexed): Management IPv4 or IPv6 address.
  * `device_type` (`VARCHAR(50)`, Not Null, Indexed): `router`, `switch`, `access_point`, `server`, `host`, `other`.
  * `building` (`VARCHAR(100)`, Not Null, Indexed): Physical campus building.
  * `department` (`VARCHAR(100)`, Not Null, Indexed): Academic or administrative department.
  * `floor` (`VARCHAR(50)`, Not Null): Floor identifier (e.g., `Floor 1`, `Basement`).
  * `location_description` (`VARCHAR(255)`, Nullable): Specific room or rack details.
  * `vendor_model` (`VARCHAR(100)`, Nullable): Hardware model (e.g., `Cisco Catalyst 9500`).
  * `snmp_community` (`VARCHAR(100)`, Default: `'public'`): Read-only community string.
  * `snmp_port` (`INTEGER`, Default: `161`): UDP port for SNMP queries.
  * `collection_method` (`VARCHAR(20)`, Default: `'snmp'`): `snmp` or `mock`.
  * `polling_interval_seconds` (`INTEGER`, Default: `30`): Periodic polling frequency.
  * `polling_enabled` (`BOOLEAN`, Default: `True`): Active polling switch.
  * `monitoring_status` (`VARCHAR(20)`, Default: `'active'`): `active`, `maintenance`, `inactive`.
  * `connection_status` (`VARCHAR(20)`, Default: `'unknown'`): `online`, `offline`, `unknown`.
  * `reachability` (`VARCHAR(20)`, Default: `'unknown'`): `reachable`, `unreachable`, `degraded`.
  * `last_seen` (`DATETIME`, Nullable): UTC timestamp of latest successful query.
  * `last_poll_at` (`DATETIME`, Nullable): UTC timestamp of last query attempt.
  * `last_poll_status` (`VARCHAR(50)`, Default: `'idle'`): `success`, `timeout`, `error`.
  * `last_poll_error` (`TEXT`, Nullable): Diagnostic error string if failed.
  * `created_at` (`DATETIME`, UTC Default): Record creation timestamp.
  * `updated_at` (`DATETIME`, UTC Default): Record update timestamp.

### 1.2 Table: `device_telemetry_history`
* **Purpose:** Time-series telemetry records collected during periodic device polling.
* **Columns:**
  * `id` (`INTEGER`, Primary Key, Autoincrement)
  * `device_id` (`VARCHAR(64)`, Indexed, Foreign Key -> `devices.id`)
  * `timestamp` (`DATETIME`, Not Null, Indexed): UTC sample timestamp.
  * `interface_name` (`VARCHAR(100)`, Not Null, Indexed)
  * `upload_mbps` (`FLOAT`, Default: `0.0`): Instantaneous outbound rate.
  * `download_mbps` (`FLOAT`, Default: `0.0`): Instantaneous inbound rate.
  * `packets_sent_per_sec` (`FLOAT`, Default: `0.0`)
  * `packets_recv_per_sec` (`FLOAT`, Default: `0.0`)
  * `total_transferred_mb` (`FLOAT`, Default: `0.0`)
  * `error_count` (`INTEGER`, Default: `0`): Interface transmission error sum.
  * `drop_count` (`INTEGER`, Default: `0`): Interface packet drop sum.
  * `collection_status` (`VARCHAR(50)`, Default: `'success'`)
  * `collection_method` (`VARCHAR(20)`, Default: `'snmp'`)

### 1.3 Table: `topology_links`
* **Purpose:** Layer-2 neighbor adjacencies discovered via LLDP and CDP.
* **Columns:**
  * `id` (`INTEGER`, Primary Key, Autoincrement)
  * `source_device_id` (`VARCHAR(64)`, Not Null, Indexed, Foreign Key -> `devices.id`)
  * `local_interface` (`VARCHAR(100)`, Not Null)
  * `remote_device_id` (`VARCHAR(64)`, Nullable, Indexed, Foreign Key -> `devices.id`)
  * `remote_chassis_id` (`VARCHAR(255)`, Not Null)
  * `remote_chassis_id_subtype` (`VARCHAR(50)`, Nullable)
  * `remote_port_id` (`VARCHAR(255)`, Not Null)
  * `remote_port_id_subtype` (`VARCHAR(50)`, Nullable)
  * `remote_port_desc` (`VARCHAR(255)`, Nullable)
  * `remote_system_name` (`VARCHAR(255)`, Nullable)
  * `remote_system_desc` (`VARCHAR(500)`, Nullable)
  * `protocol` (`VARCHAR(20)`, Default: `'lldp'`): `lldp` or `cdp`.
  * `discovered_at` (`DATETIME`, Not Null): Initial discovery timestamp.
  * `last_seen_at` (`DATETIME`, Not Null, Indexed): Most recent advertisement renewal.
  * `discovery_source` (`VARCHAR(50)`, Default: `'snmp'`): `snmp` or `mock`.
  * `resolution_state` (`VARCHAR(50)`, Default: `'unresolved'`, Indexed): `resolved` or `unresolved`.
  * `link_status` (`VARCHAR(20)`, Default: `'active'`, Indexed): `active`, `stale`, `down`.
* **Unique Composite Index:** `("source_device_id", "local_interface", "remote_chassis_id", "remote_port_id")`.

### 1.4 Table: `topology_alerts`
* **Purpose:** Audit-compliant record of Layer-2 topology change detection events and lifecycle states.
* **Columns:**
  * `id` (`VARCHAR(64)`, Primary Key, Indexed): Unique ID (e.g., `alert_2a4f61e890cd`).
  * `event_type` (`VARCHAR(50)`, Not Null, Indexed): `new_neighbor`, `neighbor_stale`, `neighbor_restored`, `interface_changed`, `protocol_changed`, `discovery_failed`, `discovery_unsupported`.
  * `severity` (`VARCHAR(20)`, Default: `'info'`, Indexed): `info`, `warning`, `critical`, `error`.
  * `status` (`VARCHAR(20)`, Default: `'open'`, Indexed): `open`, `acknowledged`, `resolved`.
  * `source_device_id` (`VARCHAR(64)`, Not Null, Indexed)
  * `source_device_name` (`VARCHAR(255)`, Nullable)
  * `remote_device_id` (`VARCHAR(64)`, Nullable, Indexed)
  * `remote_device_name` (`VARCHAR(255)`, Nullable)
  * `remote_chassis_id` (`VARCHAR(255)`, Nullable)
  * `local_interface` (`VARCHAR(100)`, Nullable)
  * `remote_port_id` (`VARCHAR(255)`, Nullable)
  * `protocol` (`VARCHAR(20)`, Nullable)
  * `message` (`VARCHAR(500)`, Not Null): Diagnostic human-readable description.
  * `details` (`TEXT`, Nullable): JSON payload containing diagnostic context.
  * `first_detected_at` (`DATETIME`, Not Null, Indexed)
  * `last_seen_at` (`DATETIME`, Not Null, Indexed)
  * `acknowledged_at` (`DATETIME`, Nullable)
  * `acknowledged_by` (`VARCHAR(100)`, Nullable)
  * `acknowledgement_note` (`VARCHAR(500)`, Nullable)
  * `resolved_at` (`DATETIME`, Nullable)
  * `resolved_by` (`VARCHAR(100)`, Nullable)
  * `resolution_note` (`VARCHAR(500)`, Nullable)
  * `occurrence_count` (`INTEGER`, Default: `1`): Deduplication hit counter.
  * `is_mock` (`BOOLEAN`, Default: `False`, Indexed)
  * `discovery_source` (`VARCHAR(50)`, Default: `'snmp'`)

### 1.5 Retention & Cascade Policies
* **Device Deletion:** Deleting a device removes the device row from `devices`. Historical telemetry and alert audit logs retain the source device ID for security compliance, avoiding accidental data loss.
* **Alert Immutability:** Alerts are **never automatically deleted** when a condition clears; they transition to `resolved` status with an audit note, preserving a permanent historical log.

---

## 2. REST API Reference

> **Authentication Note:**  
> In this academic prototype, all API endpoints are open and do not require API tokens or HTTP Authorization headers. Production deployment will require an OAuth2/JWT middleware layer.

### System & Telemetry Endpoints

#### `GET /api/v1/health`
* **Purpose:** Verifies SQLite database connection and monitoring loop state.
* **Response:**
  ```json
  {
    "status": "ok",
    "database": "connected",
    "monitoring": "running",
    "active_interface": "Wi-Fi",
    "timestamp": "2026-10-01T15:00:00Z"
  }
  ```

#### `GET /api/v1/interfaces`
* **Purpose:** Enumerates physical and virtual network interfaces detected on the host machine.
* **Response:**
  ```json
  {
    "interfaces": ["Ethernet", "Wi-Fi", "Loopback Pseudo-Interface 1"],
    "details": [{"name": "Wi-Fi", "is_up": true, "speed_mbps": 866}],
    "active_interface": "Wi-Fi",
    "count": 3
  }
  ```

#### `GET /api/v1/metrics/current`
* **Purpose:** Fetches latest real-time sample collected from the active host interface.
* **Response:**
  ```json
  {
    "timestamp": "2026-10-01T15:00:01Z",
    "interface": "Wi-Fi",
    "upload_mbps": 2.45,
    "download_mbps": 18.20,
    "packets_sent_per_sec": 140.2,
    "packets_received_per_sec": 320.8,
    "cumulative_sent_mb": 1450.2,
    "cumulative_received_mb": 8920.4,
    "session_transferred_mb": 24.5,
    "is_initial_sample": false
  }
  ```

#### `GET /api/v1/metrics/history`
* **Query Parameters:** `interface` (str), `limit` (int, 1-1000, default 100), `start_time` (ISO datetime), `end_time` (ISO datetime).
* **Response:** Array of historical metric samples matching the filters.

#### `GET /api/v1/summary`
* **Purpose:** Retrieves monitoring session overview including peak upload/download rates, session transferred data volume, and total stored records.

#### `POST /api/v1/monitoring/start`
* **Purpose:** Starts or reconfigures the background monitoring loop for a specified interface and interval.
* **Request Body (Optional):** `{"interface": "Wi-Fi", "interval_seconds": 1.0}`

#### `POST /api/v1/monitoring/stop`
* **Purpose:** Gracefully pauses the local background monitoring loop.

---

### Campus Multi-Device Registry

#### `GET /api/v1/devices`
* **Query Parameters:** `device_type`, `department`, `building`, `floor`, `monitoring_status`, `connection_status`, `search`.
* **Response:** List of registered devices matching filter criteria.

#### `GET /api/v1/devices/summary`
* **Purpose:** Computes aggregate device counts by operational status, category, and department.

#### `GET /api/v1/devices/telemetry/summary`
* **Purpose:** Computes aggregate throughput, reachability breakdown, and error totals across reporting campus devices.

#### `GET /api/v1/devices/hierarchy`
* **Purpose:** Generates nested campus topology: Campus -> Building -> Floor -> Department -> Device list.

#### `GET /api/v1/devices/telemetry/timeline`
* **Query Parameters:** `hours` (int, 1-168, default 1).
* **Purpose:** Aggregates chronological upload/download throughput across all reporting campus devices.

#### `GET /api/v1/devices/telemetry/comparison`
* **Purpose:** Compares latest telemetry rates, error counters, and reachability status across all registered devices.

#### `POST /api/v1/devices`
* **Purpose:** Registers an authorized network device in the inventory.
* **Request Body:**
  ```json
  {
    "id": "sw-science-01",
    "name": "Science-Hall-Switch-1",
    "ip_address": "10.0.5.1",
    "device_type": "switch",
    "building": "Science Hall",
    "floor": "Floor 1",
    "department": "Physics",
    "collection_method": "snmp",
    "vendor_model": "Cisco Catalyst 9300",
    "snmp_community": "public",
    "snmp_port": 161
  }
  ```
* **Response:** Created device object (HTTP 201).

#### `GET /api/v1/devices/{device_id}`
* **Purpose:** Retrieves full configuration and status details for a single registered device.

#### `PATCH /api/v1/devices/{device_id}`
* **Purpose:** Partially updates device configuration, location metadata, or monitoring status.

#### `DELETE /api/v1/devices/{device_id}`
* **Purpose:** Removes a device record from the campus registry (retains historical logs).

#### `GET /api/v1/devices/{device_id}/telemetry/latest`
* **Purpose:** Retrieves the most recent telemetry measurement recorded for a specific remote device.

#### `GET /api/v1/devices/{device_id}/telemetry/history`
* **Query Parameters:** `interface`, `limit` (default 50), `start_time`, `end_time`.
* **Purpose:** Retrieves bounded historical telemetry records for a registered campus device.

#### `GET /api/v1/devices/{device_id}/health`
* **Purpose:** Retrieves reachability state, last poll timestamp, error messages, and polling configuration.

#### `POST /api/v1/devices/{device_id}/monitoring/start`
* **Purpose:** Enables active periodic polling for a device and triggers an immediate poll attempt.

#### `POST /api/v1/devices/{device_id}/monitoring/stop`
* **Purpose:** Disables active periodic polling for a device.

---

### Network Topology Discovery

#### `GET /api/v1/topology/links`
* **Query Parameters:** `source_device_id`, `protocol` (`lldp`/`cdp`), `link_status` (`active`/`stale`/`down`), `resolution_state` (`resolved`/`unresolved`), `limit`.
* **Response:** Array of discovered links with total, resolved, unresolved, and stale counts.

#### `GET /api/v1/topology/unresolved`
* **Purpose:** Retrieves all discovered neighbors that are not registered campus devices.

#### `POST /api/v1/topology/devices/{device_id}/discover`
* **Purpose:** Initiates an immediate read-only LLDP/CDP discovery query against a registered device.
* **Response:**
  ```json
  {
    "device_id": "demo-core-01",
    "success": true,
    "status": "success",
    "protocol_used": "both",
    "neighbors_found": 3,
    "neighbors_resolved": 2,
    "message": "Discovery completed with status 'success'. Found 3 neighbors (2 resolved).",
    "duration_ms": 14.5,
    "timestamp": "2026-10-01T15:00:00Z"
  }
  ```

#### `GET /api/v1/topology/devices/{device_id}/neighbors`
* **Purpose:** Retrieves all discovered link connections originating from or connected to a given campus device.

#### `GET /api/v1/topology/devices/{device_id}/status`
* **Purpose:** Retrieves discovery execution status, protocol capabilities, and last execution results for a device.

---

### Topology Alerts & Change Detection

#### `GET /api/v1/alerts`
* **Query Parameters:** `status` (`open`/`acknowledged`/`resolved`), `severity` (`info`/`warning`/`critical`), `event_type`, `device_id`, `is_mock`, `limit`, `offset`.
* **Response:** Paginated list of alerts and summary counts.

#### `GET /api/v1/alerts/summary`
* **Purpose:** Retrieves aggregate counts of topology alerts by status, severity, and event type.

#### `GET /api/v1/alerts/{alert_id}`
* **Purpose:** Fetches complete metadata, interface mappings, and audit history for a single alert.

#### `POST /api/v1/alerts/{alert_id}/acknowledge`
* **Request Body:**
  ```json
  {
    "acknowledged_by": "Lead Network Admin",
    "note": "Verified authorized guest access point in Student Hall."
  }
  ```
* **Response:** Updated alert object with `acknowledged_at` timestamp.

#### `POST /api/v1/alerts/{alert_id}/resolve`
* **Request Body:**
  ```json
  {
    "resolved_by": "Lead Network Admin",
    "note": "Rogue cable disconnected; interface returned to standard trunk configuration."
  }
  ```
* **Response:** Updated alert object with `resolved_at` timestamp.

---

### AI Anomaly Detection & Simulation Lab

#### `GET /api/v1/anomalies`
* **Query Parameters:** `limit` (default 50), `interface`, `severity`, `start_time`, `end_time`.
* **Purpose:** Retrieves persisted network anomaly events with filtering and pagination.

#### `GET /api/v1/anomalies/latest`
* **Purpose:** Fetches the most recent anomaly evaluation event, or null if no anomalies have occurred.

#### `GET /api/v1/anomalies/summary`
* **Purpose:** Fetches anomaly detection engine operational status, training state, and event counters.

#### `GET /api/v1/simulation/scenarios`
* **Purpose:** Lists all 7 pre-configured synthetic telemetry scenarios and metadata.

#### `POST /api/v1/simulation/run`
* **Purpose:** Executes an in-memory synthetic validation scenario against an isolated Isolation Forest detector.
* **Request Body:**
  ```json
  {
    "scenario_id": "sudden_upload_spike",
    "seed": 42
  }
  ```
* **Response:**
  ```json
  {
    "scenario_id": "sudden_upload_spike",
    "name": "Sudden Upload Spike (Exfiltration Pattern)",
    "duration_seconds": 60,
    "confusion_matrix": {
      "true_positives": 15,
      "false_positives": 0,
      "true_negatives": 45,
      "false_negatives": 0,
      "total_samples": 60
    },
    "metrics": {
      "precision": 1.0,
      "recall": 1.0,
      "f1_score": 1.0,
      "accuracy": 1.0,
      "detection_latency_seconds": 1.0
    },
    "timeline": [...]
  }
  ```

#### `GET /api/v1/simulation/results`
* **Purpose:** Retrieves the most recently completed simulation validation result.

#### `POST /api/v1/simulation/reset`
* **Purpose:** Clears cached simulation validation results and resets lab state.

---

### WebSocket Endpoint: `/ws/metrics`
* **URL:** `ws://127.0.0.1:8000/ws/metrics`
* **Protocol:** WebSocket (JSON frames).
* **Broadcasting Frequency:** Every 1.0 second.
* **Frame Schema:** Contains `type` (`metric_update` or `initial_state`), `metrics` (live Mbps and packet rates), and `anomaly` (current score and severity).
