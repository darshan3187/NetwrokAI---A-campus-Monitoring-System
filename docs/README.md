# NetworkAI Documentation System
## Smart Network Monitoring & Topology Intelligence Platform

> **Academic Prototype Notice:**  
> NetworkAI is a network monitoring prototype that brings device information, traffic measurements, topology observations, and anomaly indicators into one unified dashboard. Localhost telemetry is gathered directly from host network interfaces via `psutil`. Remote device polling, SNMP collection, and LLDP/CDP discovery are implemented and tested using deterministic mock fixtures and local UDP probes; they have not been validated against live production campus hardware. Anomaly scores indicate statistical deviation, not confirmed cyberattack probabilities.

---

## Welcome to NetworkAI

**NetworkAI** is an open-source, full-stack network telemetry, discovery, and anomaly detection platform designed for academic environments and enterprise network operations centers (NOCs). It provides real-time traffic monitoring, layer-2 neighbor discovery (LLDP and CDP), automated topology event tracking with deduplication, and unsupervised machine learning (Isolation Forest) for statistical outlier detection.

```
       +-----------------------------------------------------------+
       |                  NetworkAI Dashboard                      |
       |  (Campus NOC, Live Topology, Alert Center, AI Lab)        |
       +-----------------------------+-----------------------------+
                                     |
                         WebSocket & REST APIs
                                     |
       +-----------------------------v-----------------------------+
       |                  FastAPI Backend Core                     |
       |  +---------------------+   +---------------------------+  |
       |  |  Host psutil Engine |   | Remote Polling Engine     |  |
       |  |  (Local Telemetry)  |   | (SNMP / Mock Collectors)  |  |
       |  +---------------------+   +---------------------------+  |
       |  +---------------------+   +---------------------------+  |
       |  |  Isolation Forest   |   | LLDP / CDP Discovery      |  |
       |  |  (Anomaly ML)       |   | & Alerting Engine         |  |
       |  +---------------------+   +---------------------------+  |
       +-----------------------------+-----------------------------+
                                     |
                       SQLite ACID Persistence
```

---

## Targeted Audiences & Reading Paths

NetworkAI documentation is organized into modular guides tailored to three distinct user groups:

| Audience | What You Need | Recommended Reading Path |
| :--- | :--- | :--- |
| **Complete Beginners & Non-Technical Visitors** | Intuitive analogies, basic concepts, simple definitions, and zero-jargon explanations. | 1. [01. Introduction to NetworkAI](01-introduction.md)<br>2. [02. Features & User Guide](02-features-and-user-guide.md)<br>3. [11. Technical Glossary](11-glossary.md) |
| **Students & Developers** | Setup instructions, architecture diagrams, code walkthroughs, API references, and data flows. | 1. [07. Installation & Setup Guide](07-installation-and-setup.md)<br>2. [03. How It Works (System Workflow)](03-how-it-works.md)<br>3. [04. Technical Architecture](04-system-architecture.md)<br>4. [06. Database & API Reference](06-database-and-api.md) |
| **Professors, Evaluators & Reviewers** | Problem statement, algorithm design, mathematical models, testing evidence, viva defense, limitations, and future scope. | 1. [05. AI & Network Algorithms](05-ai-and-algorithms.md)<br>2. [08. Demo & Viva Guide](08-demo-and-viva-guide.md)<br>3. [09. Testing & Reliability Audit](09-testing-and-validation.md)<br>4. [10. Limitations & Future Scope](10-limitations-and-future-scope.md) |

---

## Documentation Navigation

| Document | Purpose & Summary |
| :--- | :--- |
| [**01. Introduction**](01-introduction.md) | High-level conceptual overview explaining networks, routers, switches, telemetry, topologies, and anomalies using road network analogies. |
| [**02. Features & User Guide**](02-features-and-user-guide.md) | Comprehensive walkthrough of every frontend view: Campus NOC, Device Inventory, Topology Map, Alert Center, Simulation Lab, and Settings. |
| [**03. How It Works**](03-how-it-works.md) | End-to-end data lifecycle: counter-to-rate calculus, rollover protection, discovery cycles, neighbor resolution, and alert deduplication. |
| [**04. System Architecture**](04-system-architecture.md) | Full technical breakdown of frontend, backend, service modules, database schema, and WebSocket communication with Mermaid diagrams. |
| [**05. AI & Algorithms**](05-ai-and-algorithms.md) | Deep-dive into Isolation Forest, the 15-dimensional feature space, rolling window calculations, statistical fallback, and evaluation metrics. |
| [**06. Database & API Reference**](06-database-and-api.md) | Exhaustive REST endpoint listings, request/response schemas, SQLAlchemy model definitions, and database constraints. |
| [**07. Installation & Setup**](07-installation-and-setup.md) | Step-by-step Windows 11 installation manual covering Python venv, Node.js, Vite build, database seeding, and troubleshooting. |
| [**08. Demo & Viva Guide**](08-demo-and-viva-guide.md) | Structured 8-to-12 minute live demonstration script, elevator pitches, and 30+ rigorous viva questions with model answers. |
| [**09. Testing & Validation**](09-testing-and-validation.md) | Test report covering all 145 automated backend tests, frontend TypeScript verification, ESLint report, and concurrency safety. |
| [**10. Limitations & Future Scope**](10-limitations-and-future-scope.md) | Academic honesty disclosure detailing hardware testing boundaries, SNMPv3 absence, auth limitations, and future enhancements. |
| [**11. Glossary**](11-glossary.md) | Alphabetical encyclopedia of networking, software, and machine learning terminology used throughout the codebase. |

---

## Core Technologies

* **Backend Engine:** Python 3.10+, FastAPI, Uvicorn, asyncio
* **Telemetry & Discovery:** `psutil` (host OS interface sampling), raw UDP SNMPv2c walker (MIB-II, LLDP-MIB, CDP-MIB)
* **Machine Learning:** `scikit-learn` (Isolation Forest), `numpy` (vectorized math)
* **Database & ORM:** SQLite 3 with WAL mode, SQLAlchemy 2.0
* **Frontend Web Application:** React 19, TypeScript, Vite, Tailwind CSS, Lucide Icons, Framer Motion
* **Testing & Quality Assurance:** `pytest`, `pytest-asyncio`, `httpx`, ESLint

---

## Project Status & Verified Metrics

* **Backend Automated Test Suite:** **145 passing tests** across 13 test suites (0 failures).
* **Frontend Production Build:** Optimized build (`tsc -b && vite build`) passing with **0 errors**.
* **Frontend Linter:** Clean with **0 errors** (17 React compiler advisory notices).
* **Demo Scenarios:** 100% reproducible, idempotent seeding via [`backend/seed_demo_scenario.py`](../backend/seed_demo_scenario.py).
