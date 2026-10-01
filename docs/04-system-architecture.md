# 04 — Technical Architecture

This document provides a technical blueprint of the NetworkAI software architecture, module relationships, communication protocols, and design rationale.

---

## 1. High-Level Architecture Diagram

```mermaid
graph TB
    subgraph ClientLayer["Frontend Client (Browser)"]
        UI[React 19 + TypeScript + Tailwind SPA]
        Vite[Vite Dev & Production Bundler]
        WSClient[Native Browser WebSocket API]
    end

    subgraph APILayer["FastAPI Gateway (Uvicorn Async ASGI)"]
        REST[FastAPI REST Router /api/v1/*]
        WSEndpoint[WebSocket Endpoint /ws/metrics]
        CORS[CORSMiddleware]
    end

    subgraph ServiceLayer["Core Application Services"]
        LocalCollector[app.collector.NetworkTrafficCollector]
        MonitorService[app.services.monitoring.MonitoringService]
        PollerService[app.services.polling.DevicePollingService]
        TopoService[app.services.topology.TopologyDiscoveryService]
        AlertService[app.services.alerting.TopologyAlertService]
        AnomalyService[app.services.anomaly.AnomalyDetector]
        SimService[app.services.simulation.SimulationService]
    end

    subgraph PersistenceLayer["Database & OS Interfaces"]
        DB[(SQLite 3 Database: network_monitoring.db)]
        SQLA[SQLAlchemy 2.0 ORM Engine]
        PSUTIL[psutil OS Interface Subsystem]
        SNMPClient[Custom UDP SNMPv2c / LLDP Client]
    end

    UI -->|HTTP Requests| REST
    WSClient <-->|Live Stream Frames| WSEndpoint
    REST --> MonitorService
    REST --> PollerService
    REST --> TopoService
    REST --> AlertService
    REST --> AnomalyService
    REST --> SimService
    WSEndpoint <--> MonitorService

    MonitorService --> LocalCollector
    LocalCollector --> PSUTIL
    PollerService --> SNMPClient
    TopoService --> SNMPClient
    TopoService --> AlertService

    MonitorService --> SQLA
    PollerService --> SQLA
    TopoService --> SQLA
    AlertService --> SQLA
    SQLA --> DB
```

---

## 2. Telemetry Data Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    participant OS as Host OS Kernel
    participant Collector as NetworkTrafficCollector
    participant MonService as MonitoringService
    participant FeatureEngine as NetworkFeatureExtractor
    participant AnomalyEngine as AnomalyDetector
    participant DB as SQLite DB
    participant WS as WebSocket Clients

    loop Every 1.0 Second
        MonService->>Collector: collect(active_interface)
        Collector->>OS: psutil.net_io_counters()
        OS-->>Collector: raw (bytes_sent, bytes_recv, packets)
        Collector->>Collector: Calculate delta rates & verify rollover
        Collector-->>MonService: NetworkMetrics
        MonService->>FeatureEngine: extract(metrics)
        FeatureEngine-->>MonService: 15-Feature Vector
        MonService->>AnomalyEngine: evaluate(features)
        AnomalyEngine-->>MonService: AnomalyEvaluationResult (Score, Severity)
        MonService->>DB: INSERT INTO network_metrics
        opt If Score >= 0.60
            MonService->>DB: INSERT INTO anomaly_events
        end
        MonService->>WS: Broadcast JSON telemetry frame
    end
```

---

## 3. Topology Discovery Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant Admin as Network Admin (UI)
    participant API as /api/v1/topology/devices/{id}/discover
    participant TopoService as TopologyDiscoveryService
    participant SNMP as SNMP UDP Client
    participant AlertService as TopologyAlertService
    participant DB as SQLite DB

    Admin->>API: Trigger Discovery (POST)
    API->>TopoService: discover_device(db, device_id)
    TopoService->>DB: Load previous links (snapshot)
    alt collection_method == "snmp"
        TopoService->>SNMP: Query LLDP-MIB & CDP-MIB OIDs
        SNMP-->>TopoService: Parsed Neighbor OID Walk
    else collection_method == "mock"
        TopoService->>TopoService: Read RFC Mock Neighbor Fixtures
    end
    TopoService->>DB: Query registered devices (IPs, Names)
    TopoService->>TopoService: Resolve Neighbors (Stage 1: IP, Stage 2: Name)
    TopoService->>DB: Upsert current topology_links
    TopoService->>AlertService: process_discovery_events(prev_links, current_links)
    AlertService->>AlertService: Deduplicate against active alerts
    AlertService->>DB: Upsert topology_alerts
    TopoService-->>API: DiscoveryResult Summary
    API-->>Admin: HTTP 200 (Found N neighbors, M resolved)
```

---

## 4. Alert Lifecycle Diagram

```mermaid
stateDiagram-v2
    [*] --> OPEN: Topology Change Detected (new_neighbor, neighbor_stale, interface_changed)
    
    OPEN --> OPEN: Repeat Event Occurs (Deduplication increments occurrence_count, updates last_seen_at)
    
    OPEN --> ACKNOWLEDGED: Operator inputs name & notes (/api/v1/alerts/{id}/acknowledge)
    
    ACKNOWLEDGED --> ACKNOWLEDGED: Repeat Event Occurs (Maintains ACK status, increments count)
    
    ACKNOWLEDGED --> RESOLVED: Operator resolves with audit note (/api/v1/alerts/{id}/resolve)
    
    OPEN --> RESOLVED: Automatic Recovery (Stale link renews advertisement)
    
    RESOLVED --> [*]: Preserved permanently for historical audit trail
```

---

## 5. Anomaly Detection Engine Flow

```mermaid
flowchart TD
    RawMetric[Incoming Telemetry Sample] --> FeatExt[NetworkFeatureExtractor: 15 Features]
    FeatExt --> WarmupCheck{Samples Observed >= 20?}
    
    WarmupCheck -- No --> WarmupOut[Severity: Normal, Score: 0.00, Method: warmup]
    
    WarmupCheck -- Yes --> TrainCheck{Isolation Forest Fitted?}
    
    TrainCheck -- Yes --> ModelEval[Isolation Forest decision_function]
    ModelEval --> Sigmoid[Monotonic Sigmoid Mapping]
    Sigmoid --> ScoreOut[Normalized Score: 0.00 - 1.00]
    
    TrainCheck -- No --> Fallback[Statistical Fallback: Z-Score Deviation >= 3.0]
    Fallback --> ScoreOut
    
    ScoreOut --> SevCheck{Score Threshold}
    SevCheck -- "< 0.60" --> NormalSev[Normal Traffic]
    SevCheck -- "0.60 - 0.79" --> UnusualSev[Unusual Traffic]
    SevCheck -- ">= 0.80" --> HighSev[High Anomaly]
    
    UnusualSev --> PersistAnomaly[Persist to anomaly_events Table]
    HighSev --> PersistAnomaly
```

---

## 6. Database Entity Relationships (ERD)

```mermaid
erDiagram
    devices ||--o{ device_telemetry_history : "records telemetry"
    devices ||--o{ topology_links : "acts as source_device"
    devices ||--o| topology_discovery_status : "tracks status"
    devices ||--o{ topology_alerts : "reports alerts"

    devices {
        string id PK "Unique identifier (e.g. demo-core-01)"
        string name "Device system name"
        string ip_address UK "Management IPv4 address"
        string device_type "router | switch | access_point | server"
        string building "Campus building"
        string department "Academic department"
        string floor "Floor level"
        string collection_method "snmp | mock"
        string connection_status "online | offline | unknown"
        string monitoring_status "active | maintenance | inactive"
        string reachability "reachable | unreachable | degraded"
        datetime last_seen "Last successful response"
    }

    device_telemetry_history {
        int id PK "Autoincrement ID"
        string device_id FK "References devices.id"
        datetime timestamp "Measurement timestamp"
        float upload_mbps "Outbound rate"
        float download_mbps "Inbound rate"
        float packets_sent_per_sec "Egress packet rate"
        float packets_recv_per_sec "Ingress packet rate"
        int error_count "Interface error sum"
        string collection_status "success | timeout | error"
    }

    topology_links {
        int id PK "Autoincrement ID"
        string source_device_id FK "Discovered by this device"
        string local_interface "E.g. GigabitEthernet0/1"
        string remote_device_id FK "Nullable: references devices.id if resolved"
        string remote_chassis_id "Neighbor MAC or identifier"
        string remote_port_id "Neighbor interface name"
        string protocol "lldp | cdp"
        string resolution_state "resolved | unresolved"
        string link_status "active | stale | down"
        datetime last_seen_at "Freshness timestamp"
    }

    topology_discovery_status {
        string device_id PK "References devices.id"
        string status "idle | success | failed | unsupported"
        boolean lldp_supported "LLDP protocol capability"
        boolean cdp_supported "CDP protocol capability"
        int discovered_neighbors_count "Total neighbors found"
        int resolved_neighbors_count "Successfully resolved count"
        datetime last_discovery_at "Timestamp of last cycle"
    }

    topology_alerts {
        string id PK "Unique alert ID (e.g. alert_9a7b12)"
        string event_type "new_neighbor | neighbor_stale | interface_changed"
        string severity "info | warning | critical | error"
        string status "open | acknowledged | resolved"
        string source_device_id FK "Source reporting device"
        string remote_device_id "Target device if resolved"
        string remote_chassis_id "Chassis ID of neighbor"
        string local_interface "Port involved"
        int occurrence_count "Deduplication counter"
        boolean is_mock "Provenance flag"
        string acknowledged_by "User name"
        string resolved_by "User or System"
        datetime first_detected_at "First occurrence"
        datetime last_seen_at "Most recent occurrence"
    }

    network_metrics {
        int id PK "Autoincrement ID"
        datetime timestamp "Sample timestamp UTC"
        string interface "Host adapter name"
        float upload_mbps "Instantaneous upload"
        float download_mbps "Instantaneous download"
        float packets_sent_per_sec "Packets sent/s"
        float packets_received_per_sec "Packets recv/s"
        float cumulative_sent_mb "Total MB sent since boot"
        float cumulative_received_mb "Total MB recv since boot"
    }

    anomaly_events {
        int id PK "Autoincrement ID"
        datetime timestamp "Detection timestamp UTC"
        string interface "Host adapter name"
        float anomaly_score "0.00 to 1.00 normalized"
        string severity "Unusual Traffic | High Anomaly"
        string detection_method "isolation_forest | statistical_fallback"
        string explanation "Diagnostic reasoning text"
    }
```

---

## 7. Technology Rationale

| Layer | Chosen Technology | Architectural Rationale |
| :--- | :--- | :--- |
| **Backend Framework** | **FastAPI (Python)** | High-performance asynchronous execution, native WebSocket support, automatic OpenAPI/Swagger generation, and seamless integration with Python's scientific ecosystem (`scikit-learn`, `numpy`, `psutil`). |
| **Database** | **SQLite 3 (WAL Mode)** | Zero-configuration, serverless, self-contained single-file ACID persistence. Write-Ahead Logging (WAL) permits concurrent readers while background telemetry writers record samples, making it ideal for academic and small-to-medium institutional deployments. |
| **Telemetry Collector** | **`psutil`** | Cross-platform, mature, low-overhead C-extension reading kernel I/O counters directly without requiring administrative root privileges or raw packet-sniffing drivers (such as WinPcap/Npcap). |
| **Machine Learning** | **Isolation Forest** | Unsupervised algorithm with $O(n \log n)$ training complexity, specifically designed for anomaly detection. Unlike density estimators (e.g., GMMs) or distance-based methods (e.g., k-NN), Isolation Forest isolates anomalies using random partitioning trees without assuming normal Gaussian distributions. |
| **Frontend Framework** | **React 19 + Vite** | Component-driven declarative UI with instant Hot Module Replacement (HMR), TypeScript type safety, and optimized production chunk splitting. |
| **Styling** | **Tailwind CSS** | Utility-first styling enabling a clean, responsive, dark/light theme-adaptive enterprise NOC design system without bulky UI framework dependencies. |
