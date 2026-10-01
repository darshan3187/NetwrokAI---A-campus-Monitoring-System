# Remote Network Device Telemetry & Monitoring Engine (Phase 2)

## Overview

NetworkAI Phase 2 introduces a **safe, modular remote network device telemetry and monitoring engine**. This engine enables scheduled, non-blocking polling of registered campus network equipment (switches, routers, access points, and servers) while preserving complete isolation from the existing host-level `psutil` monitoring, AI anomaly detection pipeline, and synthetic Simulation Lab.

---

## 1. Architecture & Data Flow

```
                                  +------------------------------------+
                                  |         FastAPI REST Engine        |
                                  | (/api/v1/devices/.../telemetry)    |
                                  +-----------------+------------------+
                                                    |
                                                    v
+-----------------------+              +---------------------------+
|  Local Host psutil    |              |   DevicePollingService    |
|   (Unchanged Loop)    |              |  (Non-Overlapping Jobs)   |
+-----------+-----------+              +-------------+-------------+
            |                                        |
            v                                        v
+-----------------------+              +---------------------------+
|   network_metrics     |              |     Collector Factory     |
|    (SQLite Table)     |              +-------------+-------------+
+-----------+-----------+                            |
            |              +-------------------------+-------------------------+
            |              |                         |                         |
            |              v                         v                         v
            |     +------------------+      +------------------+      +------------------+
            |     |  Mock Collector  |      | SNMPv2c Collector|      | Local Adapter    |
            |     | (Deterministic)  |      |   (Read-Only)    |      | (psutil-based)   |
            |     +--------+---------+      +--------+---------+      +--------+---------+
            |              |                         |                         |
            |              +-------------------------+-------------------------+
            |                                        |
            |                                        v
            |                          +---------------------------+
            |                          |      RateCalculator       |
            |                          |  (Deltas, Resets, Rollover|
            |                          +-------------+-------------+
            |                                        |
            |                                        v
            |                          +---------------------------+
            |                          |     device_telemetry      |
            |                          |       (SQLite Table)      |
            |                          +-------------+-------------+
            |                                        |
            +--------------------+-------------------+
                                 |
                                 v
                +---------------------------------+
                |   WebSocket Stream (/ws/metrics)|
                |   - metric_update (Local host)  |
                |   - anomaly_event (Local AI)    |
                |   - device_telemetry (Remote)   |
                +----------------+----------------+
                                 |
                                 v
                +---------------------------------+
                |      React / Vite Frontend      |
                |  (DeviceInventory + Detail Modal|
                +---------------------------------+
```

### Core Components

1. **`BaseRemoteCollector` Interface (`backend/app/services/remote_collector/base.py`)**:
   Standardized contract returning structured `DevicePollResult` containing raw counter snapshots (`RawInterfaceCounters`) and reachability states (`configured`, `reachable`, `unreachable`, `unsupported`).

2. **`RateCalculator` (`backend/app/services/remote_collector/rate_calculator.py`)**:
   Converts raw cumulative byte/packet counters into throughput (Mbps) and packet rates (pkts/sec) using precise elapsed-time deltas. Intelligently traps initial samples, 32-bit rollovers, and device reboots (`counter_reset`) without emitting artificial spikes or negative rates.

3. **`DevicePollingService` (`backend/app/services/remote_collector/polling.py`)**:
   Central asynchronous scheduler that iterates over devices whose `polling_enabled` flag is `True`. Guarantees:
   - **Job Deduplication**: Uses an active-poll registry (`_active_polls`) to prevent overlapping polling jobs if a device responds slowly.
   - **Failure Isolation**: Wraps each device poll in an isolated task with bounded socket timeouts (default 3.0s); unreachable devices never delay or crash the scheduler.
   - **Non-blocking Execution**: Performs network I/O in async worker tasks without blocking FastAPI's primary event loop.

4. **`DeviceTelemetryModel` (`backend/app/models.py`)**:
   Independent relational table storing per-interface timestamped telemetry records with dedicated indexes on `device_id`, `interface_name`, and `timestamp`.

---

## 2. Local vs. Remote Monitoring

| Dimension | Local Host Monitoring | Remote Device Monitoring (Phase 2) |
| :--- | :--- | :--- |
| **Data Source** | Local machine kernel via Python `psutil` | Remote network targets via SNMP or Mock collector |
| **Polling Model** | Continuous 1.0s background loop on active adapter | Configurable interval per device (default 10s), enabled on-demand |
| **Database Table** | `network_metrics` | `device_telemetry` |
| **Anomaly Pipeline**| Isolation Forest running on rolling host feature vector | Dedicated telemetry storage & diagnostics (isolated from host AI) |
| **Default State** | Active upon server startup on host default interface | **Disabled (`polling_enabled: false`)** until explicitly enabled by user |
| **Authentication**| Native OS permissions | Read-only SNMP v2c/v3 community/credentials via environment variables |

---

## 3. SNMP Prerequisites & Standard IF-MIB OIDs

When configured for live hardware polling (`collection_method: 'snmp'`), the collector queries standard IETF MIB-II (`RFC 1213`) and IF-MIB (`RFC 2863`) object identifiers:

* **System Information**:
  - `sysDescr` (`1.3.6.1.2.1.1.1.0`): Hardware/OS description
  - `sysUpTime` (`1.3.6.1.2.1.1.3.0`): System uptime in hundredths of a second
* **Standard 32-Bit Counters (`ifTable`: `1.3.6.1.2.1.2.2.1`)**:
  - `ifDescr` (`.2`): Interface name / description
  - `ifOperStatus` (`.8`): Operational state (`1=up`, `2=down`, `3=testing`)
  - `ifInOctets` (`.10`): Inbound bytes
  - `ifInUcastPkts` (`.11`): Inbound unicast packets
  - `ifInErrors` (`.14`), `ifInDiscards` (`.13`): Inbound drop/error counters
  - `ifOutOctets` (`.16`), `ifOutUcastPkts` (`.17`), `ifOutErrors` (`.20`), `ifOutDiscards` (`.19`): Outbound counters
* **High-Capacity 64-Bit Counters (`ifXTable`: `1.3.6.1.2.1.31.1.1.1`)**:
  - `ifHCInOctets` (`.6`): 64-bit Inbound bytes (prevents rollover on Gigabit/10G links)
  - `ifHCOutOctets` (`.10`): 64-bit Outbound bytes
  - `ifHCInUcastPkts` (`.7`), `ifHCOutUcastPkts` (`.11`): 64-bit packet counters

---

## 4. Mandatory College IT Authorization & Ethical Guidelines

> [!CAUTION]
> **Strict Administrative Policy**:
> 1. Automated polling of campus network infrastructure without written permission from the College Network Operations Center (NOC) / IT Department is strictly prohibited.
> 2. Network scanning, port sweeps, or attempting credential guessing against campus devices violates network acceptable use policies.
> 3. NetworkAI **does not scan** the network and **will never initiate unsolicited polling**. Polling must be explicitly triggered for a specific registered target by an authorized operator.
> 4. All SNMP operations are strictly **Read-Only (`SNMP GET / GET-NEXT`)**. The system contains zero write capabilities (`SET` requests are deliberately excluded).

---

## 5. Security & Credential Configuration

To prevent credential leakage:
* Community strings and SNMP passwords are **never stored in SQLite** or transmitted to the frontend.
* Credentials are read strictly from environment variables on the backend server:

```bash
# Optional environment overrides (defaults to read-only 'public' on UDP port 161)
export SNMP_COMMUNITY="your_authorized_read_only_community"
export SNMP_PORT="161"
```

* API responses sanitize all error messages, preventing stack traces or IP topology leakage.

---

## 6. Safe Testing Using Mock Devices

For local development, testing, and college presentations without access to production routers:
1. Register a device with `collection_method: "mock"` (or use the pre-seeded mock devices).
2. The `MockRemoteCollector` generates deterministic, RFC-compliant counter progressions for simulated interfaces (`GigabitEthernet0/1`, `GigabitEthernet0/2`).
3. Click **"Start Polling"** in the UI to observe live throughput graphs, packet counters, and reachability status.
4. The UI prominently displays an amber badge:
   `MOCK / SIMULATED HARDWARE TELEMETRY — NOT LIVE CAMPUS HARDWARE`
   ensuring complete academic honesty.

---

## 7. Known Limitations

1. **Python 3.13 SNMP Library Ecosystem**:
   Native C-extensions for ASN.1 SNMP parsing are evolving for Python 3.13. The system includes socket-level connectivity verification and a mock fallback adapter when `pysnmp` binaries are absent.
2. **Sub-second Polling Overhead**:
   SNMP over UDP is not designed for millisecond sampling. The recommended polling cadence for campus equipment is 10 to 60 seconds to avoid CPU load on network switches.
3. **Firewall / NAT Boundaries**:
   If the NetworkAI server is separated from monitored switches by campus firewalls, UDP port 161 must be explicitly permitted in ACLs between the monitoring server and the target device IP.

---

## 8. How to Connect an Authorized Test Router Later

When an authorized lab router (e.g., a Cisco 2901 or Mikrotik RouterBOARD) is provided for testing:

1. **Configure Read-Only SNMP on the Router**:
   ```cisco
   enable
   configure terminal
   snmp-server community MyReadOnlyComm RO
   snmp-server location "Engineering Lab Rack 4"
   end
   write memory
   ```
2. **Export Server Credentials**:
   ```bash
   export SNMP_COMMUNITY="MyReadOnlyComm"
   ```
3. **Register the Router in NetworkAI**:
   - Go to the **Devices** page.
   - Click **Add Device**.
   - Enter the assigned IP (e.g., `192.168.10.1`), select Type `Router`, and set Collection Method to `snmp`.
4. **Initiate Polling**:
   - Open the device card, click **View Telemetry**, and click **Start Polling**.
   - NetworkAI will probe UDP 161, query interface counters, compute rates, and begin historical recording.

---

## 9. Campus Network Operations Center (NOC) Dashboard (Phase 3)

Phase 3 introduces a dedicated **Campus NOC Console** (`/campus` tab) capable of logically representing multi-building, multi-floor, and multi-department campus infrastructure.

### Logical Topology Hierarchy

Infrastructure is organized into a 5-tier logical hierarchy:

```
Campus
 └── Building (e.g., Computer Science Block, Main Admin, Central Library)
      └── Floor (e.g., Floor 1, Floor 2, Floor 3)
           └── Department (e.g., Computer Science, Electrical Engineering, Network Core)
                └── Network Device (Router / Switch / Access Point / Server)
```

Filtering is provided across all tiers:
* **Building Filter**
* **Floor Filter**
* **Department Filter**
* **Device Type Filter** (`router`, `switch`, `access_point`, `server`, `other`)
* **Reliable Status Filter** (`online`, `unreachable`, `stale`, `unknown`, `maintenance`)
* **Full-Text Search** (device name, IP address, hardware model)

### Reliable Device Status Semantics

To prevent a single temporary network blip or slow packet from incorrectly being flagged as hardware failure, status is derived through rigorous multi-criteria semantics:

| Status | Evaluation Criteria | Meaning |
| :--- | :--- | :--- |
| **`online`** | `reachability == 'reachable'` AND `last_poll_status == 'success'` within stale threshold | Device is healthy, responsive, and generating current telemetry. |
| **`unreachable`** | `reachability == 'unreachable'` OR `last_poll_status == 'error'` | Polling failed due to connectivity loss, socket timeout, or host down. |
| **`stale`** | Last successful poll timestamp is older than $\max(300\text{s}, 3 \times \text{polling\_interval})$ | Telemetry is out of date; polling was paused or samples ceased. |
| **`maintenance`** | Administratively marked with `monitoring_status == 'maintenance'` | Device is in planned downtime or servicing; alerts suppressed. |
| **`unknown`** | Device registered but `last_poll_at is None` (never polled) | No empirical poll evidence collected yet. |

### Non-Duplicative Telemetry Aggregation Math

When calculating campus-wide aggregate download and upload rates:
1. **Time-Bucket Discretization**: Telemetry samples are partitioned into chronological buckets:
   - **1-hour window**: 60-second time buckets
   - **6-hour window**: 300-second time buckets
   - **24-hour+ window**: 900-second time buckets
2. **Per-Device De-duplication**: Within each bucket, each reporting device contributes only its latest valid rate calculation ($R_{\text{down}}, R_{\text{up}}$). Multiple sample ticks from the same device inside the same bucket are never added together.
3. **Campus Sum**: $\text{Campus Throughput}(t) = \sum_{d \in \text{Reporting Devices}(t)} \text{Throughput}(d, t)$.

---

## 10. Implemented vs. Planned Capabilities

| Capability | Status | Implementation Details |
| :--- | :--- | :--- |
| **Local psutil Monitoring** | ✅ Implemented | Continuous 1.0s OS socket counter sampling with differential rate math |
| **Host AI Anomaly Detection** | ✅ Implemented | 15D feature vector, 100-tree Isolation Forest, heuristic diagnostics |
| **Controlled Simulation Lab** | ✅ Implemented | 7 synthetic scenarios, zero live packet transmission, 2x2 confusion matrix |
| **Campus Device Registry** | ✅ Implemented | Full CRUD REST APIs, SQLite relational persistence, search & filters |
| **Remote Polling Engine** | ✅ Implemented | Async non-blocking scheduler, worker concurrency, timeout safety |
| **Mock RFC-Compliant Collector** | ✅ Implemented | Deterministic interface counter simulator with explicit academic honesty badges |
| **Read-Only SNMPv2c Collector** | ✅ Implemented | UDP 161 standard MIB-II `ifTable` / `ifXTable` queries |
| **Campus NOC Overview Dashboard** | ✅ Implemented | KPI summary cards, aggregate throughput timeline, multi-device comparison |
| **Logical Topology Hierarchy** | ✅ Implemented | Campus → Building → Floor → Department → Device collapsible tree |
| **LLDP/CDP Topology Discovery (Phase 4)** | ✅ Implemented | Read-only discovery via standard LLDP/CDP MIBs, resolution, and link persistence (see `docs/TOPOLOGY_DISCOVERY.md`) |
| **SNMPv3 Full Cryptography** | ⏳ Planned | USM user auth (SHA/MD5) and privacy encryption (AES/DES) for production deployments |
| **Interactive Topology Visualization** | ⏳ Planned | Force-directed or hierarchical link graph visualization (Phase 5) |
| **College-Wide Live Deployment** | ⏳ Planned | Pending authorized campus IT network operations center credentials and physical switch access |

