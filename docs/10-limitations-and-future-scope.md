# 10 — Limitations and Future Scope

This document provides a transparent, academically honest accounting of the current boundaries, constraints, and engineering roadmap of NetworkAI.

---

## 1. Current System Limitations

### 1.1 Local Host Telemetry Scope
* **Current State:** Real-time host telemetry (upload/download Mbps, packet rates) is gathered directly from the network adapters of the workstation hosting the backend service via Python's `psutil.net_io_counters()`.
* **Limitation:** It monitors traffic traversing that specific machine. It does not provide full-packet wire sniffing across the entire campus local area network.

### 1.2 Remote Hardware Testing & Campus Network Authorization
* **Current State:** Remote device polling and LLDP/CDP discovery are implemented using RFC-compliant SNMP queries and deterministic mock fixtures (`backend/app/services/topology.py`).
* **Limitation:** The platform has **not** been validated against physical, production campus switches or enterprise routers. This design decision was made deliberately to adhere to academic ethics: students must never perform unauthorized SNMP queries, port scans, or packet probes against an institutional network.

### 1.3 SNMP Version & Protocol Security
* **Current State:** SNMP collection supports **SNMPv2c** using plaintext community strings (default: `public`).
* **Limitation:** SNMPv3 with cryptographic authentication (SHA/MD5) and payload encryption (AES/DES) is not currently implemented. On untrusted networks, SNMPv2c queries are vulnerable to eavesdropping.

### 1.4 Authentication and Access Control
* **Current State:** All REST API endpoints and WebSocket channels are open.
* **Limitation:** There is currently no user login, session management, API key enforcement, or Role-Based Access Control (RBAC). Any client capable of reaching `http://127.0.0.1:8000` can query metrics or acknowledge alerts.

### 1.5 Polling-Dependent Detection Latency
* **Current State:** Topology discovery and remote device health are refreshed periodically (default interval: 30 seconds).
* **Limitation:** Events (such as a cable disconnection or new rogue AP connection) are detected only when the next polling cycle executes. NetworkAI does not currently run an active SNMP Trap daemon or Syslog listener to receive instantaneous asynchronous push notifications.

### 1.6 Machine Learning Model Scope
* **Current State:** Isolation Forest detects statistical outliers within a 15-dimensional numerical feature space.
* **Limitations:**
  1. **Not an Attack Probability:** An anomaly score measures statistical divergence from the baseline; it is **not** a calibrated probability of a cyberattack. An authorized high-bandwidth video stream or operating system update will elevate the anomaly score.
  2. **Not Deep Packet Inspection (DPI):** The model operates strictly on Layer-3/Layer-4 metadata (throughput, packet rates, ratios). It does not inspect packet payloads or decrypt encrypted TLS/HTTPS traffic.
  3. **Synthetic Simulation Validation:** Precision and recall figures obtained in the Simulation Lab reflect synthetic, in-memory scenarios. They do not constitute certified real-world Intrusion Detection System (IDS) or DDoS mitigation benchmarks.

### 1.7 Non-Remediating (Read-Only) Architecture
* **Current State:** NetworkAI is strictly an observability and monitoring platform.
* **Limitation:** It deliberately does **not** perform automatic network remediation (such as disabling a switch port, blacklisting an IP on a firewall, or dropping routes). This design prevents autonomous systems from causing secondary outages due to false-positive classifications.

---

## 2. Planned Future Scope (Roadmap)

The following capabilities represent natural extensions for future academic research and production deployment. *None of these are claimed as currently implemented.*

| Planned Capability | Target Layer | Technical Approach |
| :--- | :--- | :--- |
| **SNMPv3 Implementation** | Telemetry Collection | Implement User-based Security Model (USM) supporting SHA-256 authentication and AES-256 payload privacy. |
| **Authentication & RBAC** | Security Layer | Integrate OAuth2 with JWT bearer tokens, enforcing role separation (e.g., `Viewer`, `Operator`, `Network Admin`). |
| **SNMP Trap & Syslog Listener** | Real-Time Ingestion | Implement an asynchronous UDP listener (ports 162 and 514) to process immediate link-down and configuration-change traps. |
| **External Alert Dispatchers** | Alerting Engine | Support automated dispatch of high-severity alerts via Webhooks, Slack channels, Discord bots, and email (SMTP). |
| **Supervised / Deep Anomaly Models** | Machine Learning | Train sequence models (LSTM or Temporal Convolutional Networks) on historical traffic to forecast seasonal campus peaks. |
| **Automated End-to-End Browser QA** | Quality Assurance | Implement automated Cypress or Playwright test suites executing across Chromium, Firefox, and WebKit headlessly. |
| **Docker & Container Orchestration** | Deployment | Provide multi-stage Dockerfiles and `docker-compose.yml` for unified single-command deployment with PostgreSQL backends. |
| **Physical Hardware Lab Validation** | Network Engineering | Validate discovery and polling in a controlled, isolated networking lab equipped with physical Cisco Catalyst and Juniper EX switches. |
