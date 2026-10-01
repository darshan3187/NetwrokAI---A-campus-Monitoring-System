# 11 — Networking and Technical Glossary

An alphabetical reference of networking concepts, software engineering patterns, machine learning algorithms, and abbreviations used throughout NetworkAI.

---

### A
* **ACID (Atomicity, Consistency, Isolation, Durability):** A set of four standard properties that guarantee database transactions are processed reliably even during crashes or power failures.
* **AI (Artificial Intelligence):** The simulation of human intelligence processes by computer systems, such as pattern recognition and statistical decision making.
* **Anomaly:** A pattern or observation that deviates significantly from established baseline behavior or historical trends.
* **API (Application Programming Interface):** A standardized set of rules and protocols that allows two different software programs (such as the React frontend and FastAPI backend) to communicate.
* **ASN.1 (Abstract Syntax Notation One):** A standard interface description language used in telecommunications and computer networking to define data structures independently of machine architecture.
* **Availability:** The percentage of time a network system, link, or device remains operational and accessible to users.

### B
* **Bandwidth:** The maximum theoretical data-carrying capacity of a network communication link, typically expressed in Megabits per second (Mbps) or Gigabits per second (Gbps).
* **BER (Basic Encoding Rules):** A standard encoding method used to convert ASN.1 data structures into a stream of raw bytes for transmission over network protocols like SNMP.
* **Bytes-per-Packet:** A calculated feature ($\frac{\text{Total Bytes}}{\text{Total Packets}}$) that helps distinguish bulk file transfers (large packets) from port scans or SYN floods (small, empty packets).

### C
* **CDP (Cisco Discovery Protocol):** A proprietary Layer-2 network protocol developed by Cisco Systems used by devices to share information about themselves with directly connected adjacent hardware.
* **Chassis ID:** A unique hardware or MAC address identifier representing the physical enclosure of a networking device.
* **Confusion Matrix:** A table used in machine learning to evaluate the performance of a classification model by comparing predicted labels against known ground-truth labels (True Positives, False Positives, True Negatives, False Negatives).
* **Contamination:** A hyperparameter in unsupervised anomaly detection (specifically Isolation Forest) that specifies the estimated proportion of outliers present in the dataset.
* **CORS (Cross-Origin Resource Sharing):** A web browser security standard that regulates whether scripts running in a browser can make HTTP requests to a domain or port different from the one serving the web page.

### D
* **DDoS (Distributed Denial of Service):** A cyberattack where multiple compromised systems flood the bandwidth or resources of a targeted server to make it unavailable to legitimate users.
* **Decision Function:** In scikit-learn, a function that outputs the signed distance of a sample to the model's separating decision boundary.
* **Deduplication:** The process of identifying duplicate or repetitive occurrences of an event and consolidating them into a single record with an incremented counter to prevent alert fatigue.
* **DPI (Deep Packet Inspection):** Advanced network packet filtering that examines the actual data payload (and optionally decrypts protocol streams) rather than just inspecting headers.

### E
* **Ethernet:** The universal family of wired computer networking technologies commonly used in local area networks (LANs), standardizing cable specifications and packet formats.

### F
* **FastAPI:** A modern, high-performance web framework for building REST and WebSocket APIs with Python based on standard type hints and asynchronous coroutines.
* **Feature Extraction:** In machine learning, the process of transforming raw measurements (like byte counters) into meaningful numerical indicators (like ratios and deviations) suitable for mathematical models.
* **F1-Score:** The harmonic mean of Precision and Recall ($2 \times \frac{P \times R}{P + R}$), providing a single balanced metric for evaluating classification accuracy.

### G
* **Gbps (Gigabits per second):** A unit of data transfer speed equal to 1,000 Megabits per second or 1,000,000,000 bits per second.

### H
* **HTTP (Hypertext Transfer Protocol):** The foundational protocol used by the World Wide Web for transferring web pages, data, and REST API messages.
* **HTTPS (Hypertext Transfer Protocol Secure):** An encrypted extension of HTTP utilizing Transport Layer Security (TLS) to safeguard sensitive web traffic.

### I
* **IEEE 802.1AB:** The formal engineering standard defining the Link Layer Discovery Protocol (LLDP).
* **Interface (Network Interface Card / NIC):** The hardware component or virtual adapter through which a computer connects to a network.
* **IP (Internet Protocol):** The primary network protocol governing how data packets are addressed and routed across network boundaries.
* **Isolation Forest:** An unsupervised machine learning algorithm based on decision trees that isolates anomalies instead of profiling normal points, functioning on the principle that anomalies require fewer random partitions to separate.

### J
* **JSON (JavaScript Object Notation):** A lightweight, human-readable data format used universally for transmitting structured data between web clients and servers.

### L
* **Latency:** The time required for a data packet to travel from its source across the network to its destination and return an acknowledgement (round-trip time).
* **LLDP (Link Layer Discovery Protocol):** A vendor-neutral Layer-2 protocol defined in IEEE 802.1AB that enables devices to advertise their identity and capabilities to directly connected neighbors.

### M
* **MAC Address (Media Access Control Address):** A unique 48-bit physical hardware identifier permanently burned into a network interface card (e.g., `00:1A:2B:3C:4D:5E`).
* **Mbps (Megabits per second):** A standard unit of data transmission rate equal to 1,000,000 bits per second or 125,000 bytes per second.
* **MIB (Management Information Base):** A hierarchical database of managed parameters and statistical counters maintained on network hardware accessible via SNMP.
* **ML (Machine Learning):** A branch of artificial intelligence focused on building applications that learn from data and improve accuracy over time without being explicitly programmed.
* **Monotonic Time:** A clock source provided by the operating system kernel that moves strictly forward and cannot be adjusted backward by system clock changes, ensuring accurate elapsed-time calculations.

### N
* **NOC (Network Operations Center):** A centralized location or dashboard where network administrators continuously supervise, monitor, and maintain telecommunications infrastructure.

### O
* **OID (Object Identifier):** An internationally standardized sequence of integers separated by dots that identifies a specific variable within an SNMP MIB tree.
* **Outlier:** A data point that differs significantly from other observations in the same sample set.

### P
* **Packet:** A discrete unit of data routed between an origin and a destination on the Internet or any packet-switched network.
* **PDU (Protocol Data Unit):** A single block of information transmitted across a network, containing protocol-specific control headers and data payloads.
* **Precision:** In classification, the ratio of correctly identified anomalies to the total number of predicted anomalies ($\frac{TP}{TP + FP}$).
* **psutil (Python System and Process Utilities):** A cross-platform Python library used to retrieve information on running processes and system utilization (CPU, memory, disks, network).

### R
* **Recall:** In classification, the ratio of correctly identified anomalies to the total number of actual anomalies present ($\frac{TP}{TP + FN}$).
* **REST (Representational State Transfer):** A software architectural style for distributed hypermedia systems commonly used to build web APIs using standard HTTP verbs (GET, POST, PATCH, DELETE).
* **Rollover (Counter Overflow):** The condition where a fixed-width binary counter (e.g., 32-bit integer) reaches its maximum capacity and wraps around to zero.
* **Router:** A Layer-3 networking device that inspects destination IP addresses and forwards packets between different networks.

### S
* **SNMP (Simple Network Management Protocol):** An Internet Standard protocol for collecting and organizing information about managed devices on IP networks.
* **SQLite:** A lightweight, C-language software library that provides a self-contained, serverless, zero-configuration transactional SQL database engine.
* **Switch:** A Layer-2 networking device that connects multiple computers within a local area network, forwarding data frames using hardware MAC addresses.

### T
* **TCP (Transmission Control Protocol):** A connection-oriented transport-layer protocol that guarantees reliable, ordered, and error-checked delivery of a stream of data packets.
* **Throughput:** The actual rate at which data is successfully transferred over a network link in real time.
* **Topology:** The physical or logical arrangement of computing devices, cables, and connections within a network.

### U
* **UDP (User Datagram Protocol):** A lightweight, connectionless transport-layer protocol that sends packets without establishing a prior connection or guaranteeing delivery order (used by SNMP and DNS).
* **UI (User Interface):** The visual screens, controls, and buttons that allow a human to interact with an application.
* **Unresolved Neighbor:** In NetworkAI, a device discovered via LLDP or CDP whose advertised IP address or system name does not match any registered campus inventory device.
* **USM (User-based Security Model):** The cryptographic security subsystem introduced in SNMPv3 to provide authentication and privacy.

### V
* **Vite:** A next-generation frontend development and bundling tool offering fast server start times and optimized production builds.

### W
* **WAL (Write-Ahead Logging):** An optimization mode in SQLite where modifications are written to a separate sequential log file before updating the main database, permitting concurrent readers while a write is underway.
* **WebSocket:** A computer communications protocol providing simultaneous full-duplex communication channels over a single persistent TCP connection.

### Z
* **Z-Score (Standard Score):** A statistical measurement that describes a value's relationship to the mean of a group of values, measured in terms of standard deviations from the mean ($Z = \frac{X - \mu}{\sigma}$).
