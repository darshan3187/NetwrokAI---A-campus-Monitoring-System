# 08 — Professor Demonstration and Viva Guide

This guide prepares students to deliver a rigorous, confident 8-to-12 minute academic presentation, demonstration, and viva voce defense of NetworkAI.

---

## 1. Quick Speech Pitches

### 30-Second Elevator Pitch
> *"Respected Professor, NetworkAI is a full-stack smart network observability platform designed for campus operations. It solves the challenge of manual network troubleshooting by combining real-time host telemetry, automated Layer-2 topology discovery using LLDP and CDP, stateful alert deduplication, and unsupervised machine learning using Isolation Forest to detect traffic anomalies. It provides administrators with a single, unified operations dashboard without requiring intrusive packet-sniffing drivers or manual threshold configuration."*

### 1-Minute Pitch
> *"Good morning, Professor. Enterprise and college campus networks comprise hundreds of routers, switches, and access points. When disruptions or traffic surges occur, administrators struggle to visualize where devices are connected and identify anomalous spikes. NetworkAI addresses this by integrating three pillars into one platform:*  
> *First, continuous telemetry collection that reads interface counters to calculate real-time upload, download, and packet rates with rollover protection.*  
> *Second, automated topology discovery using standardized LLDP and Cisco CDP protocols to map Layer-2 connections, track neighbor changes, and prevent alert spam through intelligent deduplication.*  
> *Third, an AI anomaly detection engine utilizing an Isolation Forest trained on 15 statistical features to flag outliers such as data exfiltration or scanning patterns.*  
> *All of this is backed by 145 automated tests, complete SQLite persistence, and a modern React 19 interface."*

### 3-Minute Comprehensive Summary
> *(Use this if the professor asks: "Explain your entire project concept, architecture, and results.")*  
> Cover the problem statement (monitoring visibility, manual cable tracing, alert fatigue), technical architecture (FastAPI backend, React 19 frontend, WebSocket live stream), algorithm design (Isolation Forest anomaly score mapping, counter delta finite difference calculus), topology discovery (LLDP/CDP MIB polling and neighbor resolution), and testing validation (145 passing pytest tests, 0 build errors). Conclude by emphasizing academic honesty: highlighting that local host telemetry is real, while campus devices in the demo scenario use explicitly labeled deterministic mock fixtures.

---

## 2. Structured 8–12 Minute Live Demonstration Script

| Time | Stage | What to Show on Screen | What to Say (Script) | Likely Professor Question & Best Answer |
| :---: | :--- | :--- | :--- | :--- |
| **0:00 - 1:30** | **Introduction & Problem Statement** | Slide or [docs/README.md](README.md) overview. | *"Respected evaluators, modern campus networks suffer from visibility blind spots and alert fatigue. NetworkAI unites telemetry, topology discovery, and AI anomaly detection."* | **Q:** Does this monitor the whole college right now?<br>**A:** *"No, sir. In this prototype, live telemetry is collected from this host machine via `psutil`. Remote campus devices are represented via mock fixtures to demonstrate multi-building scale safely."* |
| **1:30 - 3:00** | **Campus NOC View** | Click **Campus NOC** tab. Show Building Hierarchy and Throughput Timeline. | *"Here in the Campus NOC, we see our multi-device fleet organized hierarchically by Campus, Building, Floor, and Department. The timeline aggregates throughput across devices over 1, 6, and 24-hour windows."* | **Q:** How do you aggregate timeline data?<br>**A:** *"We query `device_telemetry_history` grouped by time buckets, summing upload and download rates across active reporting devices."* |
| **3:00 - 4:30** | **Topology Map & Discovery** | Click **Topology** tab. Drag nodes, click on the orange dashed link. | *"This is our dynamic Layer-2 topology map. Notice the solid links connecting Core to Distribution switches, and this amber dashed link. That is an unresolved neighbor detected via LLDP with MAC `00:50:56:AA:BB:CC`. Our resolution algorithm matched known devices and isolated this unmanaged guest AP."* | **Q:** What is the difference between LLDP and CDP?<br>**A:** *"LLDP is the IEEE 802.1AB vendor-neutral standard, whereas CDP is Cisco's proprietary protocol. NetworkAI queries both MIBs via SNMP to support heterogeneous environments."* |
| **4:30 - 6:00** | **Alert Lifecycle & Deduplication** | Click **Alerts** tab. Click an Open alert -> Acknowledge -> Resolve. | *"NetworkAI detects link changes between discovery cycles. Here is a `new_neighbor` alert. Notice our deduplication engine: if the condition repeats, it increments `occurrence_count` without creating duplicate rows. I will now acknowledge this alert as 'Lead Admin', and you can see the audit trail record the timestamp."* | **Q:** How do you prevent duplicate alerts?<br>**A:** *"We use a composite key of `(source_device_id, event_type, local_interface, remote_chassis_id, is_mock)`. If an open or acknowledged alert matches, we update the timestamp and counter instead of inserting."* |
| **6:00 - 7:30** | **AI Anomaly Detection** | Click **AI Anomaly** tab. Show 15-feature table and score gauge. | *"Our AI engine extracts 15 statistical features every second, including z-score deviations, bytes-per-packet, and upload/download ratios. An Isolation Forest evaluates structural outliers. Notice our score of 0.04 represents steady normal traffic."* | **Q:** Why use Isolation Forest instead of a fixed threshold like 50 Mbps?<br>**A:** *"Fixed thresholds fail because 50 Mbps might be normal on a 1 Gbps link during daytime, but anomalous at 3 AM. Isolation Forest adapts to multivariate patterns like sudden ratio inversions without static rules."* |
| **7:30 - 9:30** | **Simulation Lab** | Click **Simulation Lab**. Select `Sudden Upload Spike`, click **Run**. | *"To validate our ML model safely without risking campus network downtime, we built the Simulation Lab. This executes an in-memory synthetic burst. In 1 second, it computes the Confusion Matrix: 15 True Positives, 0 False Positives, giving 100% precision and recall on this scenario."* | **Q:** Are these scores attack probabilities?<br>**A:** *"No, sir. We are academically strict: anomaly score measures statistical divergence from baseline, not proof of an attack. High throughput during an OS update also scores high."* |
| **9:30 - 11:00** | **Testing & Architecture** | Show terminal with `pytest` (145 passed) and [04-system-architecture.md](04-system-architecture.md). | *"The system is backed by 145 automated backend tests covering API contracts, concurrency locks, rollover math, and alert lifecycles. The frontend build compiles cleanly with zero errors."* | **Q:** How do you handle counter resets?<br>**A:** *"If current bytes are less than previous bytes, the collector detects rollover, re-baselines the sample, and outputs 0.0 Mbps, preventing negative rates."* |
| **11:00 - 12:00** | **Conclusion & Limitations** | Conclude with limitations and future scope. | *"In conclusion, NetworkAI demonstrates full-stack observability from hardware counters to ML inference. Future work will introduce SNMPv3 encryption and JWT role-based access control."* | **Q:** Excellent presentation. Thank you. |

---

## 3. Comprehensive Viva Voce Questions & Model Answers (30 Questions)

### Networking Fundamentals

#### 1. What is SNMP, and which version did you implement?
> **Answer:** Simple Network Management Protocol (SNMP) is an application-layer protocol used to monitor and manage network devices over UDP port 161. In NetworkAI, we implemented **SNMPv2c** using community-based authentication (e.g., `public`) and custom ASN.1 Basic Encoding Rules (BER) serialization to query standard MIB-II, LLDP-MIB, and CDP-MIB object identifiers.

#### 2. What is an OID and a MIB?
> **Answer:** A **MIB (Management Information Base)** is a hierarchical database of manageable objects on a network device. An **OID (Object Identifier)** is a dot-separated numeric address that uniquely identifies a specific variable within that tree, such as `1.3.6.1.2.1.2.2.1.10` for interface inbound octets.

#### 3. What is LLDP (IEEE 802.1AB)?
> **Answer:** Link Layer Discovery Protocol is a vendor-neutral Layer-2 protocol. Network switches and routers periodically broadcast advertisements containing their chassis ID, port ID, system name, and capabilities to directly connected adjacent neighbors.

#### 4. What is CDP, and why support both LLDP and CDP?
> **Answer:** Cisco Discovery Protocol is Cisco's proprietary Layer-2 discovery protocol. Many enterprise campus networks run Cisco switches alongside other vendors (like Aruba or HP). By supporting both, NetworkAI successfully discovers neighbors regardless of vendor diversity.

#### 5. How does NetworkAI calculate upload and download bandwidth?
> **Answer:** It samples cumulative byte counters from the OS kernel at discrete intervals using `psutil`. It computes the delta bytes, multiplies by 8 to convert to bits, and divides by elapsed monotonic time in seconds and $10^6$ to calculate Megabits per second (Mbps).

#### 6. What is a counter reset or rollover, and how do you handle it?
> **Answer:** If a network adapter disconnects, the machine reboots, or a 32-bit integer overflows ($2^{32}-1$), the current counter will be smaller than the previous counter. Without protection, this yields negative speeds. NetworkAI detects `current < previous`, resets the baseline to the current counter, and records `0.0 Mbps` for that single interval.

#### 7. What is the difference between throughput and bandwidth?
> **Answer:** Bandwidth is the maximum theoretical capacity of a channel (e.g., a 1 Gbps NIC). Throughput is the actual volume of data successfully transmitted across the channel per unit of time (e.g., 25 Mbps during active browsing).

#### 8. What does "Stale" mean in the Topology Map?
> **Answer:** A stale link means that a neighbor previously seen on a switch port was not observed during the latest discovery cycle (its advertisement timer expired). It indicates an unrefreshed advertisement, **not** a confirmed physical wire cut. If the neighbor renews advertisements, it returns to active.

#### 9. How does NetworkAI resolve discovered neighbors?
> **Answer:** It uses a two-stage matching engine: First, it compares the neighbor's advertised IP against registered device IPs in the database. If that fails, it normalizes the advertised system name and matches it against device names or IDs. If no match is found, it labels the node as an "Unresolved Neighbor."

#### 10. Why is Layer-2 topology discovery read-only?
> **Answer:** For safety and security. NetworkAI queries standard read-only SNMP MIBs. It never writes configurations (SNMP SET), never executes active subnet port scans, and never executes commands that could disrupt campus network switching.

---

### Software Architecture & Web Engineering

#### 11. Why did you choose FastAPI over Flask or Django?
> **Answer:** FastAPI is built on Starlette and Pydantic, providing asynchronous ASGI performance with native `async/await` coroutines. It provides built-in WebSocket support for real-time streaming and automatically generates interactive Swagger/OpenAPI documentation.

#### 12. Why React 19 and Vite for the frontend?
> **Answer:** React provides declarative component reusability and fine-grained state reactivity. Vite uses native ES modules during development for sub-second Hot Module Replacement (HMR) and utilizes Rollup for optimized production chunk bundling.

#### 13. Why use WebSockets instead of periodic HTTP polling for real-time telemetry?
> **Answer:** HTTP polling requires opening a new TCP handshake and sending HTTP headers every second, introducing latency and server overhead. WebSockets maintain a persistent, bidirectional full-duplex TCP connection, enabling the server to push low-latency 1-second JSON frames directly to all connected clients.

#### 14. Why SQLite instead of PostgreSQL or MySQL?
> **Answer:** SQLite is serverless, zero-configuration, and fully ACID-compliant. In Write-Ahead Logging (WAL) mode, readers do not block writers. For an academic demonstration and single-server campus NOC deployment, SQLite provides maximum portability and zero deployment friction.

#### 15. What is the database schema structure?
> **Answer:** It comprises 7 tables: `devices` (hardware registry), `device_telemetry_history` (polling time-series), `topology_links` (Layer-2 adjacencies), `topology_discovery_status` (per-device discovery state), `topology_alerts` (audit lifecycle records), `network_metrics` (host telemetry), and `anomaly_events` (ML detection log).

#### 16. How is thread safety ensured during alert deduplication?
> **Answer:** `TopologyAlertService` wraps database lookup and insertion within a Python `threading.Lock()` mutex, ensuring that concurrent polling threads cannot produce duplicate alerts for the same event simultaneously.

#### 17. What happens when a device is deleted from the inventory?
> **Answer:** The device record is removed from `devices`. Historical telemetry and topology alerts retain the device ID to maintain security audit compliance rather than corrupting historical logs.

#### 18. What is CORS and why is CORSMiddleware configured in FastAPI?
> **Answer:** Cross-Origin Resource Sharing is a browser security mechanism that blocks web pages from making requests to a different domain or port. Because Vite runs on `http://localhost:5173` and FastAPI runs on `http://127.0.0.1:8000`, CORSMiddleware explicitly permits the frontend to access backend REST and WebSocket routes.

---

### Machine Learning & Algorithms

#### 19. Why use Isolation Forest for network anomaly detection?
> **Answer:** Isolation Forest is an unsupervised tree ensemble with $O(n \log n)$ time complexity. Unlike distance-based algorithms (like k-NN) that require expensive pairwise distance computations, Isolation Forest randomly isolates anomalies using fewer partitions. It requires no labeled attack datasets and makes no Gaussian distribution assumptions.

#### 20. What is the contamination parameter in Isolation Forest?
> **Answer:** Contamination is the expected proportion of outliers in the dataset. In NetworkAI, it is set to `0.05` ($5\%$), which sets the decision threshold for the tree ensemble during model fitting.

#### 21. How do you convert the raw tree output into a 0.00 to 1.00 score?
> **Answer:** `scikit-learn` outputs a signed decision distance. We pass this distance through a steep, monotonic sigmoid function: $S = \frac{1}{1 + e^{12 \times d}}$, clamping extreme values to prevent floating-point overflow. A decision distance of $+0.25$ maps to $\approx 0.05$ (normal), while $-0.15$ maps to $\approx 0.86$ (high anomaly).

#### 22. What are the 15 features extracted by the feature engineering engine?
> **Answer:** 
> 1. Download Mbps  
> 2. Upload Mbps  
> 3. Total Mbps  
> 4. Packets Received/sec  
> 5. Packets Sent/sec  
> 6. Total Packets/sec  
> 7. Upload/Download Ratio  
> 8. Packet Ratio  
> 9. Bytes Per Packet  
> 10. Rolling Mean Mbps  
> 11. Rolling Std Dev Mbps  
> 12. Mbps Z-Score Deviation  
> 13. Rolling Mean Packets  
> 14. Rolling Std Dev Packets  
> 15. Packet Z-Score Deviation  

#### 23. What is the warm-up period, and why is it necessary?
> **Answer:** The warm-up period is set to 20 samples. When monitoring starts, the rolling window is empty. Evaluating samples immediately would flag normal traffic as anomalous due to high initial variance. Deferring alerts for 20 seconds allows the baseline to stabilize.

#### 24. What is the statistical fallback?
> **Answer:** If the model has not yet been fitted (e.g., during startup or on zero-variance idle adapters), NetworkAI uses a deterministic rule: if traffic exceeds 2 Mbps or 100 packets/sec and the z-score deviation exceeds 3.0 standard deviations, it assigns an `Unusual Traffic` severity score.

#### 25. Is an anomaly score an attack probability?
> **Answer:** **No.** An anomaly score is strictly a measure of statistical divergence from recent baseline behavior. Legitimate events, such as downloading a large Linux ISO or starting a video stream, will elevate the score without being malicious.

#### 26. What is the purpose of the Simulation Lab?
> **Answer:** It provides a controlled, sandboxed environment to evaluate the ML model against 7 pre-scripted synthetic network scenarios (e.g., upload spikes, port scans, recovery dynamics). It computes Precision, Recall, and Confusion Matrices in memory without sending packets across real campus infrastructure.

#### 27. How does NetworkAI handle division by zero in metric calculations?
> **Answer:** Precision and Recall formulas check whether denominators ($TP + FP$ or $TP + FN$) equal zero. If so, they return `None` (mathematically undefined) rather than crashing or returning arbitrary 0.0 or 1.0 values.

---

### Project Scope, Limitations & Future Work

#### 28. What are the primary limitations of the current implementation?
> **Answer:** 
> 1. Local telemetry is collected from the single host machine running the backend.  
> 2. Campus devices in the demo scenario use mock collectors because we do not have administrative authorization to connect to physical college switches.  
> 3. SNMPv2c is implemented; encrypted SNMPv3 is planned.  
> 4. User authentication and role-based access control (RBAC) are not yet implemented.  
> 5. NetworkAI is strictly read-only; it does not perform automated port shutdowns or firewall changes.

#### 29. Why doesn't NetworkAI automatically block infected devices or shut down ports?
> **Answer:** Because automated remediation based on statistical anomaly detection can trigger catastrophic false-positive outages (e.g., shutting down a campus server because an administrator started a legitimate large file transfer). NetworkAI adheres to NOC best practices by alerting human operators rather than enforcing autonomous network changes.

#### 30. What are the key areas for future enhancement?
> **Answer:** 
> 1. Integrating SNMPv3 with USM (User-based Security Model) authentication and AES encryption.  
> 2. Adding OAuth2 / JWT authentication with role-based access (Viewer vs. Network Admin).  
> 3. Integrating Syslog and SNMP Trap daemon receivers.  
> 4. Email, Slack, or webhook alert notifications.  
> 5. Validating remote SNMP polling against physical Cisco or Juniper laboratory switches.

---

## 4. Final Conclusion for the Professor
> *"In summary, NetworkAI demonstrates that modern network observability does not require proprietary, multi-thousand-dollar enterprise suites. By uniting standard SNMP MIBs, modern asynchronous web engineering, and unsupervised machine learning, we have built a transparent, reliable, and mathematically rigorous platform. We welcome your questions and evaluation."*
