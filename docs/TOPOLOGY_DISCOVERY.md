# Authorized Read-Only Network Topology Discovery (Phase 4)

## Overview

NetworkAI Phase 4 introduces **authorized, read-only network topology discovery** leveraging standard **LLDP (IEEE 802.1AB)** and, where supported by network equipment, **CDP (Cisco Discovery Protocol)**.

This subsystem allows network administrators and NOC operators to discover physical and logical interconnections between campus routers, switches, and access points without modifying device configurations or performing unauthorized network sweeps.

---

## 1. Critical Safety & Security Rules

To ensure academic and operational safety within educational and enterprise campus networks, Phase 4 strictly enforces the following principles:

1. **Explicit Target Query Only (Zero Subnet Scanning):** Discovery is strictly performed against registered devices that exist in the NetworkAI inventory. Subnet scanning, IP range sweeping, and automated host crawling are strictly prohibited.
2. **Read-Only Access:** The engine only issues standard SNMP read-only queries (GetRequest / GetNextRequest) on standard UDP port 161. Zero configuration changes, write requests, or CLI exec commands are ever sent.
3. **Zero Credential Exposure:** SNMP community strings and security secrets are accessed exclusively through server environment variables (e.g., `SNMP_COMMUNITY`). Secrets are never persisted in plain text, logged, or returned in REST API responses.
4. **Transparent Mock Separation:** Simulated mock topology links are explicitly tagged with `discovery_source = "mock"` and `is_mock = true`. Mock links are never conflated with live hardware telemetry.
5. **No Phantom Devices:** Unregistered or external devices discovered via neighbor tables (e.g. unmanaged lab access points) are recorded as `unresolved` with `remote_device_id = null`. The engine never invents phantom device records in the primary campus registry.
6. **Honest Reporting:** When target equipment does not support LLDP/CDP MIB tables, the engine reports an honest `unsupported` status rather than fabricating physical links.

---

## 2. Architecture & Data Flow

```
+-----------------------------------------------------------------------------------+
|                            NetworkAI REST API Client                             |
|               (/api/v1/topology/links, /api/v1/topology/devices/...)               |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        TopologyDiscoveryService (Central Engine)                  |
+-----------------------------------------+-----------------------------------------+
                                          |
          +-------------------------------+-------------------------------+
          | (if collection_method = 'mock')                               | (if collection_method = 'snmp')
          v                                                               v
+------------------------------------+                         +------------------------------------+
|        MockTopologyProvider        |                         |     SafeSNMPv2cTopologyClient      |
|  - Deterministic RFC Interconnects |                         |  - Pure-Python UDP/161 client      |
|  - Fault Injection (timeout, etc.) |                         |  - IEEE 802.1AB & Cisco CDP MIBs   |
+-----------------+------------------+                         +-----------------+------------------+
                  |                                                              |
                  +-------------------------------+------------------------------+
                                                  |
                                                  v
                              +---------------------------------------+
                              |         Neighbor Resolution Engine    |
                              |  1. Match IP against Registered Devices |
                              |  2. Match System Name / Hostname      |
                              |  3. Unresolved (Preserve Remote Info) |
                              +-------------------+-------------------+
                                                  |
                                                  v
                              +---------------------------------------+
                              |            Database Persistence       |
                              |  - topology_links (Idempotent Upsert) |
                              |  - topology_discovery_status          |
                              +---------------------------------------+
```

---

## 3. Discovered Protocols & MIB Support

### IEEE 802.1AB LLDP (Link Layer Discovery Protocol)
LLDP is an open, vendor-neutral IEEE standard operating at Layer 2.

- **Base OID:** `1.0.8802.1.1.2` (iso.std.iso8802.ieee802dot1.ieee802dot1mibs.lldpMIB)
- **Local System:** `lldpLocSysName` (`...1.2.1`), `lldpLocSysDesc` (`...1.2.2`)
- **Local Port Table:** `lldpLocPortTable` (`...1.3.7`)
- **Remote Systems Table:** `lldpRemTable` (`...1.4.1`)
  - `lldpRemChassisIdSubtype` (`...1.4.1.1.4`)
  - `lldpRemChassisId` (`...1.4.1.1.5`)
  - `lldpRemPortIdSubtype` (`...1.4.1.1.6`)
  - `lldpRemPortId` (`...1.4.1.1.7`)
  - `lldpRemPortDesc` (`...1.4.1.1.8`)
  - `lldpRemSysName` (`...1.4.1.1.9`)
  - `lldpRemSysDesc` (`...1.4.1.1.10`)

### Cisco Discovery Protocol (CDP)
CDP is a proprietary Cisco Layer 2 protocol supported across Catalyst, Nexus, and ISR routers/switches.

- **Base OID:** `1.3.6.1.4.1.9.9.23` (ciscoCdpMIB)
- **CDP Neighbor Table:** `cdpCacheTable` (`...1.2.1.1`)
  - `cdpCacheAddress` (`...1.2.1.1.4`)
  - `cdpCacheDeviceId` (`...1.2.1.1.6`)
  - `cdpCacheDevicePort` (`...1.2.1.1.7`)
  - `cdpCachePlatform` (`...1.2.1.1.8`)

---

## 4. Database Schema

### `topology_links` Table
Persists discovered physical and logical link observations:

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | String(64) | PRIMARY KEY | UUID identifier |
| `source_device_id` | String(64) | FOREIGN KEY (devices.id) | Registered device where neighbor was observed |
| `local_interface` | String(100) | NOT NULL | Local interface name (e.g. `GigabitEthernet0/1`) |
| `remote_device_id` | String(64) | FOREIGN KEY (devices.id), NULLABLE | Mapped registered device ID, or NULL if unresolved |
| `remote_chassis_id` | String(100) | NOT NULL | Chassis identifier (MAC, IP, or chassis name) |
| `remote_chassis_id_subtype`| String(50) | NULLABLE | Chassis subtype (e.g. `mac_address`, `network_address`) |
| `remote_port_id` | String(100) | NOT NULL | Remote port identifier (e.g. `GigabitEthernet0/24`) |
| `remote_port_id_subtype` | String(50) | NULLABLE | Port subtype (e.g. `interface_name`, `locally_assigned`)|
| `remote_port_desc` | String(255) | NULLABLE | Port description string |
| `remote_system_name` | String(100) | NULLABLE | Neighbor sysName or hostname |
| `remote_system_desc` | String(255) | NULLABLE | Neighbor operating system or hardware description |
| `protocol` | String(20) | NOT NULL | Discovery protocol (`lldp` or `cdp`) |
| `discovered_at` | DateTime | NOT NULL | Timestamp when link was first discovered |
| `last_seen_at` | DateTime | NOT NULL | Timestamp of most recent discovery observation |
| `discovery_source` | String(20) | NOT NULL | Collector source (`snmp` or `mock`) |
| `resolution_state` | String(20) | NOT NULL | `resolved` (mapped to device) or `unresolved` |
| `link_status` | String(20) | NOT NULL | Operational status (`active`, `stale`, `down`) |

**Unique Constraint:** `(source_device_id, local_interface, remote_chassis_id, remote_port_id)` ensures repeated discoveries update timestamps idempotently without duplicating link records.

### `topology_discovery_status` Table
Tracks discovery execution history and protocol support per registered device:

| Column | Type | Description |
|---|---|---|
| `device_id` | String(64) | PRIMARY KEY, FOREIGN KEY (devices.id) |
| `status` | String(50) | `idle`, `in_progress`, `success`, `failed`, `unsupported`, `empty` |
| `protocol` | String(50) | Configured protocol (`lldp`, `cdp`, `both`) |
| `lldp_supported` | Boolean | True if device responded to LLDP MIB queries |
| `cdp_supported` | Boolean | True if device responded to CDP MIB queries |
| `discovered_neighbors_count` | Integer | Total neighbors found during last run |
| `resolved_neighbors_count` | Integer | Number of neighbors mapped to registered devices |
| `last_discovery_at` | DateTime | Timestamp of last execution |
| `last_discovery_duration_ms` | Float | Execution elapsed time in milliseconds |
| `last_error` | String(255) | Sanitized error description if discovery failed |

---

## 5. Neighbor Resolution Algorithm

When a device discovery run receives raw neighbor entries from LLDP or CDP:

1. **IP Candidate Resolution:** The engine extracts IP candidates from `raw_address` or `remote_chassis_id` and checks against registered devices (`ip_address`).
2. **System Name Resolution:** If no IP matches, the engine compares `remote_system_name` against registered device `name` and `id` (case-insensitively).
3. **Self-Loop Prevention:** An observation cannot resolve to its own `source_device_id`.
4. **Resolution Outcome:**
   - If matched: `remote_device_id` is set to the matching `DeviceModel.id`, and `resolution_state = "resolved"`.
   - If not matched: `remote_device_id = None`, and `resolution_state = "unresolved"`.
5. **No Phantom Creation:** The engine never generates dummy records in `DeviceModel` for unresolved neighbors.

---

## 6. Stale Link Management

Links are automatically classified according to observation freshness:

- **Active (`link_status = 'active'`):** The link was observed in a recent discovery run.
- **Stale (`link_status = 'stale'`):** The link has not been observed within the configured freshness threshold (default: 3600 seconds / 1 hour).
- **Scheduled Stale Sweep:** `topology_service.mark_stale_links(db, stale_threshold_seconds=3600.0)` transitions unobserved links to stale without deleting historical topology data.

---

## 7. REST API Endpoints

### 1. `GET /api/v1/topology/links`
Retrieves all discovered topology links with optional filtering.

**Query Parameters:**
- `source_device_id` (optional): Filter links originating from a specific device.
- `protocol` (optional): Filter by `lldp` or `cdp`.
- `link_status` (optional): Filter by `active`, `stale`, `down`.
- `resolution_state` (optional): Filter by `resolved` or `unresolved`.
- `limit` (optional, default: 100): Maximum records to return.

**Response (200 OK):**
```json
{
  "total_links": 2,
  "resolved_links": 1,
  "unresolved_links": 1,
  "stale_links": 0,
  "links": [
    {
      "id": "link-uuid-1",
      "source_device_id": "dev-core-router-01",
      "local_interface": "GigabitEthernet0/1",
      "remote_device_id": "dev-dist-switch-01",
      "remote_chassis_id": "00:1A:2B:3C:4D:01",
      "remote_port_id": "GigabitEthernet0/24",
      "protocol": "lldp",
      "discovery_source": "mock",
      "resolution_state": "resolved",
      "link_status": "active",
      "is_mock": true,
      "is_stale": false,
      "discovered_at": "2026-09-30T17:00:00Z",
      "last_seen_at": "2026-09-30T17:20:00Z"
    }
  ],
  "timestamp": "2026-09-30T17:25:00Z"
}
```

### 2. `GET /api/v1/topology/unresolved`
Retrieves all neighbor connections that remain unmapped to registered campus devices.

**Response (200 OK):**
```json
{
  "total_unresolved": 1,
  "unresolved_neighbors": [
    {
      "id": "link-uuid-2",
      "source_device_id": "dev-core-router-01",
      "local_interface": "GigabitEthernet0/2",
      "remote_device_id": null,
      "remote_chassis_id": "00:50:56:AB:CD:EF",
      "remote_port_id": "eth0",
      "remote_system_name": "unregistered-ap-floor2",
      "protocol": "lldp",
      "discovery_source": "mock",
      "resolution_state": "unresolved",
      "link_status": "active",
      "is_mock": true,
      "is_stale": false
    }
  ],
  "timestamp": "2026-09-30T17:25:00Z"
}
```

### 3. `POST /api/v1/topology/devices/{device_id}/discover`
Triggers an immediate authorized read-only LLDP/CDP discovery against a registered device.

**Response (200 OK):**
```json
{
  "device_id": "dev-core-router-01",
  "success": true,
  "status": "success",
  "protocol_used": "lldp",
  "neighbors_found": 2,
  "neighbors_resolved": 1,
  "message": "Discovery completed with status 'success'. Found 2 neighbors (1 resolved).",
  "duration_ms": 12.45,
  "timestamp": "2026-09-30T17:25:00Z"
}
```

### 4. `GET /api/v1/topology/devices/{device_id}/neighbors`
Retrieves all discovered neighbors where the specified device is either the source or the remote destination.

### 5. `GET /api/v1/topology/devices/{device_id}/status`
Retrieves the execution status, protocol capabilities, and historical execution summary for a specific device.

---

## 8. Limitations and Operational Constraints

1. **Layer 2 Boundary:** LLDP and CDP operate strictly across single Layer 2 broadcast domains. Routed Layer 3 hops do not transmit LLDP/CDP frames unless specifically tunneled.
2. **Campus Firewall Policies:** UDP port 161 (SNMP) must be permitted between the NetworkAI backend server and the target network management interface.
3. **Vendor Specifics:** Some managed switches require LLDP to be explicitly enabled in device configuration (`lldp run` in Cisco IOS / `lldp enable` in HP/Aruba).
4. **Deferred to Phase 5:** Interactive graph visualization and topology alert notifications are planned for Phase 5.
