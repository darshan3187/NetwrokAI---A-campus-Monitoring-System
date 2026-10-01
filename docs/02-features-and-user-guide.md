# 02 — Features and Complete User Manual

This manual provides an operational guide for every view and interactive control in the NetworkAI dashboard.

---

## 1. Dashboard Navigation & Layout Overview

The user interface consists of three persistent zones:
1. **Left Sidebar:** Primary navigation across operational tabs with status indicators.
2. **Top Header:** System health status indicator (Connected/Degraded), active interface pill, monitoring toggle switch, theme selector (Light/Dark/System), and manual refresh button.
3. **Main Content Viewport:** The active view rendered with smooth, reactive animations.

---

## 2. Key Status Definitions

Understanding status terms used throughout the system:

| Status Term | Context | Exact Meaning |
| :--- | :--- | :--- |
| **Online** | Device Inventory & Campus NOC | The device responded successfully to the most recent poll query. |
| **Unreachable** | Device Inventory & Campus NOC | Network query timed out or returned connection refused; device is not responding on its configured IP/port. |
| **Maintenance** | Device Inventory | Administrator intentionally suspended active polling for this device. |
| **Unknown** | Device Inventory | Device was registered but has not yet completed its initial polling cycle. |
| **Active (Link)** | Topology Map | Discovered neighbor advertisement was received and verified within the recent discovery cycle. |
| **Stale (Link)** | Topology Map | Previously observed neighbor advertisement was not renewed in the latest discovery cycle. Indicates unrefreshed advertisement, **not** a confirmed physical wire cut. |
| **Open** | Alert Center | New topology event detected; requires administrative awareness. |
| **Acknowledged** | Alert Center | A network operator verified the event and assigned their name and diagnostic notes. |
| **Resolved** | Alert Center | Condition restored to normal (e.g., stale link renewed) or administratively closed with resolution audit trail. |
| **Mock / Simulated** | Any View | Explicit academic labeling indicating synthetic records, deterministic test fixtures, or in-memory simulation runs. |

---

## 3. View-by-View Operations

### 3.1 Overview (Main Dashboard)
* **Purpose:** High-level executive overview of host telemetry, quick traffic metrics, and system throughput.
* **What You See:**
  * **Metric KPI Cards:** Real-time Download Mbps, Upload Mbps, Packets Received/sec, Packets Sent/sec, and Total Session Volume.
  * **Live Throughput Chart:** Dynamic time-series chart streaming instantaneous upload and download curves.
  * **Network Adapters Widget:** Quick view of the active host interface and IP configuration.
  * **Anomaly Status Widget:** Compact summary of recent AI anomaly events and current model status.
* **Data Provenance:** **Real host machine telemetry** collected locally via Python's `psutil`.

---

### 3.2 Campus NOC (Campus Operations Center)
* **Purpose:** Multi-building campus infrastructure health and fleet-wide metric aggregation.
* **What You See:**
  * **Campus KPI Summary:** Total Managed Devices, Online Count, Fleet Reachability %, and Active Alert Count.
  * **Aggregate Throughput Timeline:** Multi-hour chronological graph displaying combined upload and download throughput across all reporting campus devices with `1h`, `6h`, and `24h` range selectors.
  * **Campus Hierarchy Tree:** Visual breakdown organized as:  
    `Campus -> Building -> Floor -> Department -> Device Cards`
* **How to Use:**
  * Click on a building node to expand or collapse contained floors.
  * Use time-range filters on the timeline chart to inspect historical fleet volume.
* **Backend Processing:** Fetches `/api/v1/devices/hierarchy`, `/api/v1/devices/telemetry/timeline`, and `/api/v1/devices/summary`.
* **Data Provenance:** Aggregates registered devices; demo devices use deterministic **mock** collectors.

---

### 3.3 Topology Map (`Topology` Tab)
* **Purpose:** Visual representation of layer-2 neighbor adjacencies discovered via LLDP and CDP.
* **What You See:**
  * **Interactive Canvas:** Draggable nodes representing campus routers, switches, and access points.
  * **Visual Link Styling:**
    * *Solid Green/Cyan Lines:* Active, verified links between registered campus devices.
    * *Amber Dashed Lines:* Unresolved neighbors (devices detected via LLDP/CDP that are not registered in the inventory, such as unmanaged guest access points).
    * *Dotted Dim Lines:* Stale links whose advertisements expired.
  * **Details Drawer:** Clicking any link opens a drawer detailing local interface, remote chassis MAC, remote port ID, protocol (`lldp`/`cdp`), and freshness timestamps.
  * **Provenance Banner:** Amber notice explicitly disclosing whether active nodes are simulated fixtures.
* **How to Use:**
  * Click and drag nodes to arrange topology.
  * Click **Run Discovery** on any node to initiate an immediate read-only LLDP/CDP SNMP poll.
* **Backend Processing:** Queries `/api/v1/topology/links` and `/api/v1/topology/unresolved`.
* **Data Provenance:** Discovered via SNMP MIB tables; seeded demo environment uses **deterministic mock discovery**.

---

### 3.4 Alert Center (`Alerts` Tab)
* **Purpose:** Audit-compliant topology change tracking and operational alert management.
* **What You See:**
  * **Summary KPI Cards:** Open Alerts count, Acknowledged count, Resolved count, and Total Audit Records.
  * **Filter Controls:** Status tabs (`All`, `Open`, `Acknowledged`, `Resolved`), Severity dropdown (`Info`, `Warning`, `Critical`), and Event Type filters (`new_neighbor`, `neighbor_stale`, `neighbor_restored`, `interface_changed`).
  * **Alert Detail Cards:** Displays source device, remote chassis, interface, protocol, exact event timestamp, repeat occurrence count, and full audit logs.
* **How to Use (Lifecycle Progression):**
  1. Click an **Open** alert card to expand its action buttons.
  2. Click **Acknowledge**, enter your name (e.g., *"Lead Operator"*) and an investigation note. The alert transitions immediately to **Acknowledged** status.
  3. When resolved, click **Resolve Alert**, enter resolution details, and confirm. The alert moves to **Resolved** status, preserving all timestamps and user names.
* **Backend Processing:** Calls `/api/v1/alerts/{id}/acknowledge` and `/api/v1/alerts/{id}/resolve`. Deduplication prevents duplicate alert creation on repetitive events.

---

### 3.5 Device Inventory (`Devices` Tab)
* **Purpose:** Complete administrative registry of campus network hardware.
* **What You See:**
  * Search bar (matches name, IP, department, vendor, or building).
  * Filter dropdowns by Device Type (`switch`, `router`, `access_point`, `server`), Building, and Operational Status.
  * Device table displaying name, IP address, device type, location, collection method badge (`SNMP` vs `MOCK`), reachability indicator, and action buttons.
* **How to Use:**
  * Click **Add Device** to register a new switch or router with IP, building, floor, department, and collection credentials.
  * Click the **View / Details** icon on any row to open the **Device Detail Modal**.
  * Click **Start/Stop Polling** to toggle background polling.

---

### 3.6 Device Detail Modal
* **Purpose:** Comprehensive deep-dive into a single device's configuration and telemetry.
* **What You See:**
  * **Overview Tab:** System name, IP, vendor model, location hierarchy, collection method, and polling status.
  * **Telemetry History Tab:** Time-series charts showing download/upload throughput and packet counts for this device.
  * **Discovery Status Tab:** Discovered LLDP/CDP neighbors count, protocol support (`LLDP`, `CDP`), and last discovery timestamp.
  * **Interface Links Tab:** List of all direct layer-2 connections originating from this device.

---

### 3.7 AI Anomaly Engine (`AI Anomaly` Tab)
* **Purpose:** Real-time visibility into the machine learning outlier detection pipeline.
* **What You See:**
  * **Detector Status Banner:** Displays calibration state (`Warming Up`, `Active`, `Statistical Fallback`).
  * **Anomaly Score Gauge:** Normalized anomaly score from `0.00` to `1.00`.
  * **Severity Indicators:** `Normal` (< 0.60), `Unusual Traffic` (0.60 - 0.79), `High Anomaly` (>= 0.80).
  * **Feature Snapshot Table:** Live values of the 15 extracted features (throughput deviations, packet ratios, bytes-per-packet).
  * **Diagnostic Explanation:** Human-readable reasoning explaining why an observation was flagged (e.g., *"Download throughput surged 5.2x standard deviations above rolling baseline"*).
* **Data Provenance:** Evaluates real host interface telemetry in real time.

---

### 3.8 Simulation Lab (`Simulation Lab` Tab)
* **Purpose:** Controlled, academic validation of the Isolation Forest algorithm against synthetic network scenarios without generating real network attacks or packet floods.
* **Available Scenarios:**
  1. `Normal Baseline`: Steady web traffic verification (zero false alarms).
  2. `Gradual Increase`: Workload trend drift testing.
  3. `Sudden Download Spike`: High-volume inbound surge.
  4. `Sudden Upload Spike`: Outbound exfiltration ratio inversion.
  5. `Unusual Packet Rate`: Small-packet port scan pattern.
  6. `Bidirectional Burst`: Simultaneous bidirectional stress.
  7. `Return to Baseline`: System self-clearing recovery dynamics.
* **How to Use:**
  1. Select a scenario from the dropdown.
  2. Click **Run Simulation**.
  3. Inspect the Confusion Matrix (True Positives, False Positives, True Negatives, False Negatives), Precision, Recall, F1-Score, and step-by-step evaluation timeline.
* **Data Provenance:** **100% Synthetic in-memory simulation**; isolated completely from host adapters and SQLite database.

---

### 3.9 Live Stream, Analytics, Interfaces & Settings
* **Live Stream:** High-frequency, unbuffered real-time throughput graph driven by direct WebSocket feed (`/ws/metrics`).
* **Analytics:** Long-term historical query tool with custom date-range pickers and CSV export capabilities.
* **Interfaces:** Technical list of all physical and virtual network adapters detected on the host machine by `psutil`, showing MAC addresses, speed, and status.
* **Settings:** Configuration panel for WebSocket reconnection intervals, theme selection, and system preferences.

---

## 4. Practical Walkthrough: 5-Minute Demonstration Scenario

Follow these steps to demonstrate the complete platform:
1. **Initialize Demo State:** Run `python backend/seed_demo_scenario.py`.
2. **Open Dashboard:** Navigate to `http://localhost:5173`.
3. **Verify Fleet in Campus NOC:** Click **Campus NOC**; show the 4 seeded switches across Main Admin, Science Hall, Engineering, and Data Center.
4. **Show Topology Adjacency:** Click **Topology**; highlight the solid links between `demo-core-01` and its distribution switches, and point out the amber dashed link to the unmanaged guest access point.
5. **Demonstrate Alert Lifecycle:** Click **Alerts**; show the open unmanaged AP alert, click **Acknowledge**, add your name and note, and verify it updates in the audit trail.
6. **Demonstrate Algorithm Validation:** Click **Simulation Lab**, run `Sudden Upload Spike`, and explain how the confusion matrix proves precision and recall without risking live network downtime.
