# Academic Demonstration Guide & Faculty Presentation Script

**Project Title:** Smart Network Monitoring AI  
**Presentation Duration:** 5–7 Minutes  
**Target Audience:** Computer Networks & Applied Machine Learning Faculty Evaluation Panel

---

## Demonstration Script & Step-by-Step Flow

```
[0:00 - 0:45] Step 1: Problem Introduction
[0:45 - 1:30] Step 2: System Architecture Overview
[1:30 - 2:15] Step 3: Application Launch & Live Hardware Telemetry
[2:15 - 3:00] Step 4: AI Anomaly Detection & Warm-up Phase
[3:00 - 4:15] Step 5: Controlled Synthetic Simulation Lab Execution
[4:15 - 5:15] Step 6: Confusion Matrix & Validation Metric Analysis
[5:15 - 6:00] Step 7: Honest Technical Limitations & Design Trade-offs
[6:00 - 6:45] Step 8: Future Scope & Conclusion
```

---

### Step 1: Introduce the Problem (0:00 – 0:45)
* **What to say**:
  > *"Good morning/afternoon professors. Traditional network monitoring tools rely heavily either on Deep Packet Inspection (DPI)—which introduces heavy CPU overhead, privacy violations, and requires root permissions—or on static rule thresholds that trigger false alarms whenever traffic spikes legitimately. Furthermore, evaluating anomaly detection models in an academic or enterprise setting is hazardous: you cannot simply launch real SYN floods or volumetric DDoS attacks on the campus network without disrupting services.
  > 
  > Our project, **Smart Network Monitoring AI**, solves this by combining non-intrusive host socket telemetry collection via `psutil`, an unsupervised scikit-learn `IsolationForest` engine with multi-dimensional temporal feature engineering, and a safe, in-memory **Simulation Lab** for reproducible statistical validation."*

---

### Step 2: Explain the Architecture (0:45 – 1:30)
* **What to show**: Display the Mermaid architecture diagram from the README or slide.
* **What to say**:
  > *"The architecture is separated into three distinct layers:
  > 1. **Telemetry & Collection Layer**: A Python background collector polls OS network socket counters (`psutil.net_io_counters`) at 1 Hz, applying differential mathematics with counter rollover and zero-division guards.
  > 2. **AI & API Backend**: A FastAPI service persists metrics into SQLite (WAL mode enabled), extracts a 15-dimensional feature vector, evaluates anomaly scores via Isolation Forest, and streams enriched live JSON payloads over WebSockets.
  > 3. **Presentation & Simulation Layer**: A React 19 + TypeScript dashboard provides real-time Recharts visualizations, and connects to an isolated Simulation Lab engine that tests synthetic scenarios without touching physical network hardware."*

---

### Step 3: Start the Application & Show Live Telemetry (1:30 – 2:15)
* **What to execute in terminal**:
  ```powershell
  # Terminal 1: Backend
  python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

  # Terminal 2: Frontend
  cd frontend
  npm run dev
  ```
* **What to show in browser (`http://localhost:5173`)**:
  * Open the **Overview** tab.
  * Point out the green **LIVE** and **WS** indicators.
  * Show the active interface badge (e.g., `Wi-Fi`).
  * Point to the live cards: Download Mbps, Upload Mbps, Session Volume, and Packet Rate.
* **What to say**:
  > *"Here is the live dashboard running against actual host telemetry. As we browse the web or transfer data, our background collector computes differential rates each second. The WebSocket receives the latest telemetry and updates our Recharts rolling line chart smoothly without full-page reloads."*

---

### Step 4: Explain Anomaly Scoring and Model Warmup (2:15 – 3:00)
* **What to show**: Click on the **AI Anomaly** tab or live score indicator.
* **What to say**:
  > *"Rather than looking at throughput alone, our feature engineering module converts each sample into a 15-dimensional vector containing rates, upload/download ratios, packet ratios, average bytes-per-packet, and rolling standard deviations ($Z$-score proxy).
  > 
  > During the first 30 seconds, the model is in **Baseline Calibration Phase**—it accumulates clean normal samples to fit 100 Isolation Trees without raising false alarms. Once calibrated, tree path lengths map to an anomaly score between 0.0 and 1.0. A score below 0.60 is classified as Normal; between 0.60 and 0.80 is Unusual Traffic; and above 0.80 triggers a High Anomaly alert with human-readable diagnostic explanations."*

---

### Step 5: Open the Simulation Lab & Run Scenario (3:00 – 4:15)
* **What to show**:
  * Click on the **Simulation Lab** tab in the sidebar.
  * Select the scenario: **Sudden Download Spike** (or **Sudden Upload Spike / Exfiltration**).
  * Confirm Seed is set to `42`.
  * Click the cyan **Run Scenario** button.
  * Watch the execution complete in ~2 seconds.
* **What to say**:
  > *"To safely validate how the model responds to extreme events without flooding our physical Wi-Fi adapter, we built the Simulation Lab. This runs strictly in memory against an isolated model instance.
  > 
  > We have just executed the 'Sudden Download Spike' scenario. At step 32, inbound throughput surges 16x from 8.5 Mbps to 140 Mbps for 11 seconds before returning to baseline."*

---

### Step 6: Explain Confusion Matrix & Validation Metrics (4:15 – 5:15)
* **What to show**: Scroll to the KPI Cards and 2x2 Confusion Matrix on screen.
* **What to say**:
  > *"The lab automatically calculates standard statistical measures against the labeled ground truth:
  > * **True Positives (11)**: All 11 burst steps were flagged instantly.
  > * **False Negatives (0)**: Yielding a **Recall of 100%**.
  > * **Detection Latency (0.0s)**: The anomaly was identified on the very first onset step ($t=32$).
  > * **True Negatives (47)** and **False Positives (2)**: Notice the two false positives occurring at steps 50 and 51. This is a real architectural insight: our feature extractor maintains a 30-step rolling window. When the spike ends, the lingering rolling mean contrasted against returned baseline rates creates a structural feature mismatch that briefly scores above threshold before normalizing.
  > * Furthermore, our framework correctly handles undefined metric semantics: in scenarios with zero actual anomalies like `normal_stable`, precision and recall are properly reported as `null/undefined` rather than manufactured 0% or 100% scores."*

---

### Step 7: Explain Limitations Honestly (5:15 – 6:00)
* **What to say**:
  > *"As computer network engineers, we must be technically honest about limitations:
  > 1. **No Packet Payload Inspection**: Because we operate at the OS socket level via `psutil`, we monitor interface volume and packet rates, but cannot inspect encrypted payload contents.
  > 2. **Concept Drift vs. False Alarms**: When traffic increases smoothly over time (as demonstrated in our `gradual_increase` scenario), a static Isolation Forest baseline will eventually flag high sustained throughput as out-of-distribution. In our Phase 5.2 investigation, we tested online retraining but proved that it risks severe baseline poisoning by stealthy attackers.
  > 3. **Prototype Status**: This system is an academic research prototype and does not claim DDoS defense certification."*

---

### Step 8: Conclude with Future Scope (6:00 – 6:45)
* **What to say**:
  > *"In future work, we plan to extend this architecture with:
  > * Distributed collector agents streaming to a centralized Kafka or Redis bus.
  > * eBPF integration for per-process socket attribution on Linux.
  > * Automated mitigation triggers via local firewall packet filters.
  > 
  > Thank you for your time. We are now happy to answer your questions."*

---

## Likely Faculty Questions & Technically Accurate Answers

### Q1: *"Why did you use Isolation Forest instead of a neural network or simple threshold?"*
**Answer**:
> *"Simple thresholds only track a single metric (e.g. download > 100 Mbps) and fail on ratio-based anomalies such as low-throughput data exfiltration (where download is low but upload/download ratio is severely inverted) or port scans (high packet count with tiny payloads).
> 
> Deep learning models (like LSTM autoencoders) require large GPU resources, slow inference, and thousands of training epochs. `IsolationForest` operates in $\mathcal{O}(n \log n)$ time, runs lightweight on commodity CPU cores, isolates anomalies near the root of shallow trees without assuming normal Gaussian distributions, and works well on tabular multi-feature vectors."*

### Q2: *"How do you calculate throughput accurately using `psutil`?"*
**Answer**:
> *"We sample `psutil.net_io_counters(pernic=True)` at discrete intervals. Let $t_1, t_2$ be monotonic timestamps and $B_1, B_2$ be cumulative byte counters. The throughput is:
> $$\text{Throughput (Mbps)} = \frac{(B_2 - B_1) \times 8}{(t_2 - t_1) \times 10^6}$$
> We guard against three key real-world edge cases:
> 1. **First measurement tick**: $B_1$ is established as a baseline; no rate is computed until the second tick.
> 2. **Zero/Negative elapsed time**: Guards against timer skew by checking $\Delta t > 0.001\text{s}$.
> 3. **Counter rollover**: If $B_2 < B_1$ (e.g. system 32/64-bit integer overflow or adapter reboot), we reset the baseline smoothly rather than computing negative throughput."*

### Q3: *"Does the Simulation Lab generate real traffic that could interfere with other computers?"*
**Answer**:
> *"No, absolutely not. The Simulation Lab operates **100% in memory**. The synthetic generator constructs Python dictionaries conforming to the `NetworkMetrics` schema and passes them directly to an isolated `AnomalyDetector` instance. Zero raw sockets, zero UDP/TCP packets, and zero OS network system calls are dispatched. The physical Wi-Fi or Ethernet adapter is completely untouched."*

### Q4: *"Why do precision and recall show as 'Undefined' on the normal stable scenario?"*
**Answer**:
> *"In binary classification, Precision is $\frac{TP}{TP + FP}$ and Recall is $\frac{TP}{TP + FN}$. When evaluating a normal traffic scenario where there are zero actual anomaly steps ($TP + FN = 0$) and zero alarms raised ($TP + FP = 0$), both formulas yield $\frac{0}{0}$.
> 
> In Phase 5.2, we corrected a common statistical error where systems arbitrarily coerce $0/0$ to $1.0$ or $0.0$. Coercing to $1.0$ falsely implies $100\%$ precision when no positive alarms were made; coercing to $0.0$ implies failure. Reporting them as `null / Undefined` is mathematically rigorous. Accuracy remains well-defined: $\frac{0 + 50}{50} = 100\%$."*

### Q5: *"Why did you observe false positives after a sudden spike ended?"*
**Answer**:
> *"Our `NetworkFeatureExtractor` uses a 30-sample rolling window deque to compute rolling averages and standard deviations. When an 11-second burst occurs, high throughput samples remain in that rolling buffer for 30 seconds.
> When traffic drops back to 8.5 Mbps baseline, the instantaneous throughput is low while the rolling mean is still $\sim 58\text{ Mbps}$. This multi-metric mismatch pushes the sample into a low-density region in the Isolation Forest feature space for 2 seconds (steps 50 and 51) until the old burst samples roll completely out of the buffer."*

### Q6: *"How do you prevent the database from filling up during an ongoing attack?"*
**Answer**:
> *"In `backend/app/services/monitoring.py`, we implement an **alert throttling policy**. When an anomaly is detected, an event is persisted to SQLite at most once every 10 seconds for an ongoing anomaly of constant severity. However, if severity escalates from 'Unusual Traffic' to 'High Anomaly', the system bypasses throttling to persist the escalation immediately."*
