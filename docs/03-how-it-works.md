# 03 — How It Works: Complete System Workflow

This document traces the complete technical data journey of NetworkAI from raw operating system counters and network packets to interactive UI visualization.

---

## 1. High-Level Data Journey

```
+---------------------------------------------------------------------------------+
|                                 DATA SOURCES                                    |
|   [ Host OS NICs via psutil ]       [ Remote Network Devices via SNMP / Mock ]  |
+------------------------+------------------------------------+-------------------+
                         |                                    |
                         v                                    v
+------------------------+------------------------------------+-------------------+
|                           FASTAPI SERVICE LAYER                                 |
|                                                                                 |
|   1. Local Collector (app/collector.py)                                         |
|      - Counter delta math, rollover protection, throughput calculation          |
|                                                                                 |
|   2. Feature Extractor & Anomaly Engine (app/services/anomaly.py)               |
|      - 15 features, rolling statistics, Isolation Forest inference              |
|                                                                                 |
|   3. Remote Poller & Topology Engine (app/services/topology.py)                 |
|      - Read-only SNMP queries, LLDP/CDP MIB parsing, neighbor resolution        |
|                                                                                 |
|   4. Alerting Engine (app/services/alerting.py)                                 |
|      - Lifecycle tracking (Open->Ack->Resolved), stateful deduplication         |
+------------------------+------------------------------------+-------------------+
                         |                                    |
                         v                                    v
+------------------------+------------------------------------+-------------------+
|                        STORAGE & REAL-TIME DISPATCH                             |
|                                                                                 |
|   [ SQLite Database (WAL Mode) ]              [ WebSocket Streamer (/ws/metrics) ]
|   - network_metrics                           - Sub-second live updates         |
|   - anomaly_events                            - Concurrent client broadcasting  |
|   - devices & topology_links                                                    |
|   - topology_alerts                                                             |
+------------------------------------+--------------------------------------------+
                                     |
                                     v
+------------------------------------+--------------------------------------------+
|                          REACT 19 FRONTEND CLIENT                               |
|   - Campus NOC, Topology Canvas, Alert Center, Live Stream, AI Lab              |
+---------------------------------------------------------------------------------+
```

---

## 2. What Happens When the Application Starts Up (Startup Lifecycle)

When you run `uvicorn app.main:app` and `npm run dev`, the system executes an automated 5-step startup sequence:

```text
[1. Database Check]    --> Initializes SQLite tables in WAL mode if not already created.
[2. Interface Probe]   --> Uses psutil to inspect all physical/virtual network adapters on your PC.
[3. Primary Selection] --> Identifies the most active adapter (e.g., Wi-Fi or Ethernet) by total traffic.
[4. Collector Launch]  --> Starts background async loops:
                           - Local telemetry loop (samples host NIC every 1.0 second).
                           - Remote device poller (polls registered devices every 30 seconds).
[5. WebSocket Open]    --> Opens the /ws/metrics endpoint, ready to push live frames to browser clients.
```

When your browser loads `http://localhost:5173`, the React application immediately establishes a WebSocket connection. Within 1 second, the first live telemetry frame arrives, and charts begin streaming without manual page refreshes.

---

## 3. Detailed Technical Workflows

### A. Local Host Telemetry Collection
* **Input:** Operating system kernel network interface counters sampled every 1.0 second via `psutil.net_io_counters(pernic=True)`.
* **Processing:**
  1. Retrieves raw numbers: `bytes_sent`, `bytes_recv`, `packets_sent`, `packets_recv`, `errin`, `errout`, `dropin`, `dropout`.
  2. Compares against the immediately preceding sample.
  3. Computes time elapsed using high-resolution monotonic timestamps (`time.monotonic()`).
* **Output:** `NetworkMetrics` data structure containing instantaneous upload/download Mbps and packet rates.
* **Storage:** Persisted to SQLite table `network_metrics`.
* **User-Visible Result:** Live numbers and streaming charts in the **Overview** and **Live Stream** views.
* **Limitations:** Captures traffic traversing the local host running the backend; does not capture traffic on other computers across the room.

---

### B. Counter-to-Rate Calculation & Rollover Protection
* **Problem:** Network cards do not measure "speed." They only maintain cumulative counters counting every byte since the computer booted.
* **Formula:**
  $$\text{Throughput (Mbps)} = \frac{(\text{Current Bytes} - \text{Previous Bytes}) \times 8}{\text{Elapsed Seconds} \times 1,000,000}$$
* **Rollover & Reset Safeguard:**
  * If a computer reboots, an adapter disconnects, or a 32-bit hardware register overflows ($2^{32}-1$ bytes), the current counter value becomes *smaller* than the previous sample.
  * *Standard formula would produce a negative speed (e.g., -450 Mbps).*
  * **NetworkAI Safeguard:** The collector detects `current_bytes < previous_bytes`, suppresses the calculation, resets the baseline sample to the current point, and outputs `0.0 Mbps` for that single interval.

---

### C. Remote Device Polling
* **Input:** Inventory records in the `devices` table with configured IP addresses and polling intervals (default: 30 seconds).
* **Processing:**
  * Background async loop (`polling_service`) polls each active device periodically.
  * For SNMP devices: dispatches non-blocking UDP queries.
  * For Mock devices: reads deterministic RFC-compliant simulated telemetry fixtures.
* **Output:** Metric sample with interface throughput, packet counts, and reachability.
* **Storage:** Saved in `device_telemetry_history`; updates `last_poll_status` in `devices`.
* **User-Visible Result:** Device status indicators in **Campus NOC** and **Device Inventory**.

---

### D. SNMP Collection Architecture
* **Input:** Target device IP address, UDP port (default: 161), and SNMP community string (e.g., `public`).
* **Protocol Used:** **SNMPv2c** using minimal custom ASN.1 BER (Basic Encoding Rules) PDU serialization.
* **Processing:**
  1. Constructs an SNMP `GetNextRequest` or `GetRequest` PDU packet.
  2. Sends packet to UDP port 161 with a bounded 2.0-second socket timeout.
  3. Parses the incoming response PDU to extract MIB-II variable bindings (`ifInOctets`, `ifOutOctets`, `sysName`).
* **Limitations:** SNMPv2c transmits community strings in plaintext across the local network segment. SNMPv3 (encrypted authentication) is planned for future iterations.

---

### E. Topology Discovery (LLDP & CDP)
* **Input:** Authorized registered switch or router ID.
* **Processing:**
  1. Queries standardized Layer-2 discovery MIB trees:
     * **LLDP MIB:** `1.0.8802.1.1.2.1.4.1.1` (Chassis ID, Port ID, System Name)
     * **CDP MIB:** `1.3.6.1.4.1.9.9.23.1.2.1.1` (Device ID, Device Port, Platform)
  2. Extracts neighbor chassis identifiers, remote port names, and management IP addresses.
* **Output:** List of `DiscoveredNeighbor` records.
* **Storage:** Updates `topology_links` and `topology_discovery_status`.

---

### F. Neighbor Resolution Algorithm
* **Problem:** A switch reports that it sees neighbor chassis `00:1A:2B:CC:DD:01`. How does the system know which campus device that is?
* **Two-Stage Resolution Engine:**
  1. **Stage 1 (IP Candidate Matching):** Tests if the neighbor's advertised management IP matches any registered device's `ip_address` in the `devices` table.
  2. **Stage 2 (System Name / ID Matching):** Normalizes the advertised `sysName` and compares it case-insensitively against registered device `name` and `id` records.
* **Result Classification:**
  * **Resolved:** Matched to an existing device record; `remote_device_id` is linked.
  * **Unresolved:** Device is an external, unmanaged, or rogue device (e.g., a student's personal router or guest AP). Preserved as an unmanaged neighbor with its raw chassis MAC address.

---

### G. Topology Change Detection
* **Processing:** Between discovery cycles $T_1$ and $T_2$, the engine takes an immutable snapshot of all previous links on that device and compares them against newly discovered links:
  * **New Link Observed:** Neighbor present in $T_2$ but absent in $T_1$.
  * **Neighbor Stale:** Neighbor present in $T_1$ but missing in $T_2$ (exceeded advertisement window).
  * **Neighbor Restored:** Neighbor was previously stale but renewed its advertisement in $T_2$.
  * **Interface Shift:** Known neighbor moved from port `Gi0/1` to `Gi0/2`.
  * **Protocol Switch:** Neighbor switched advertisement from CDP to LLDP.

---

### H. Alert Generation & Stateful Deduplication
* **Problem:** If a neighbor remains unrefreshed across 50 polling cycles, an unsophisticated monitoring tool would spam the operator with 50 duplicate alert rows.
* **NetworkAI Deduplication Engine:**
  * When a change occurs, `alert_service` queries active alerts matching:  
    `source_device_id + event_type + local_interface + remote_chassis_id + is_mock`  
    where `status IN ('open', 'acknowledged')`.
  * **If an active alert exists:** The database does **not** insert a new row. It increments `occurrence_count` by 1 and updates `last_seen_at`.
  * **If no active alert exists:** Generates a new unique alert ID (e.g., `alert_3f8a12bc90de`) and inserts an `open` record.
* **Thread Safety:** Protected by internal mutex locks to prevent race conditions during concurrent polls.

---

### I. Alert Lifecycle (Open -> Acknowledged -> Resolved)
* **Lifecycle Rules:**
  1. **OPEN:** Newly generated alert.
  2. **ACKNOWLEDGED:** Operator assigns their name and diagnostic notes. Alert remains visible but indicates human awareness.
  3. **RESOLVED:**
     * *Manual:* Operator verifies physical repair and marks resolved with audit notes.
     * *Automatic Recovery:* If a stale neighbor renews its advertisement, the system automatically transitions open/acknowledged `neighbor_stale` alerts to `resolved` with `resolved_by="System (Auto-recovery)"`.

---

### J. AI Anomaly Detection Pipeline
* **Input:** Latest `NetworkMetrics` telemetry sample.
* **Stage 1 (Feature Extraction):** Transforms raw numbers into 15 statistical features:
  * Raw throughputs (download, upload, total Mbps).
  * Packet rates (received, sent, total packets/sec).
  * Ratio features (upload/download ratio, packet ratio, bytes-per-packet).
  * Rolling statistics (30-sample rolling mean, standard deviation, and normalized z-score deviations).
* **Stage 2 (Warm-up Period):** The first 20 samples populate the baseline buffer. Alarms are deferred during warm-up to prevent initial false positives.
* **Stage 3 (Inference):**
  * Evaluated via **Isolation Forest** (100 isolation trees, 5% contamination).
  * Tree decision distance is converted into a normalized score ($0.00$ to $1.00$) via a smooth monotonic sigmoid.
  * If the model is not yet fitted, a deterministic statistical fallback (3.0+ std dev) acts as a safety net.
* **Output:** Anomaly evaluation score, severity (`Normal`, `Unusual Traffic`, `High Anomaly`), and human-readable explanation.

---

### K. Simulation Lab Workflow
* **Design Philosophy:** Complete architectural isolation.
* **Execution:**
  1. Instantiates a completely separate, in-memory `AnomalyDetector` instance.
  2. Feeds pre-scripted synthetic telemetry vectors (e.g., 60 seconds of traffic with a 15-second burst).
  3. Evaluates predictions against known ground-truth labels.
  4. Calculates a formal statistical Confusion Matrix:
     $$\text{Precision} = \frac{TP}{TP + FP}, \quad \text{Recall} = \frac{TP}{TP + FN}, \quad F_1 = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$
* **Safety:** Zero bytes written to the database; zero packets sent to physical network adapters.
