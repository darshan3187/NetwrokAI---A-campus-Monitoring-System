# 05 — AI and Network Algorithms

This document provides a mathematical and algorithmic deep-dive into NetworkAI's telemetry rate calculus, feature engineering, machine learning anomaly detection, and stateful deduplication.

---

## 1. Telemetry Rate Calculus

Network cards and operating systems maintain cumulative monotonically increasing counters. To calculate instantaneous throughput, the collector applies finite difference calculus over discrete time steps.

### Mathematical Formulation

Given two consecutive telemetry samples $S_1$ at monotonic time $t_1$ and $S_2$ at monotonic time $t_2$:

$$\Delta t = t_2 - t_1 \quad (\text{seconds})$$
$$\Delta B_{\text{sent}} = B_{\text{sent}}(t_2) - B_{\text{sent}}(t_1) \quad (\text{bytes})$$
$$\Delta B_{\text{recv}} = B_{\text{recv}}(t_2) - B_{\text{recv}}(t_1) \quad (\text{bytes})$$

Converting bytes into Megabits ($1 \text{ Byte} = 8 \text{ bits}$, $1 \text{ Mbit} = 1,000,000 \text{ bits}$):

$$\text{Upload Throughput (Mbps)} = \frac{\Delta B_{\text{sent}} \times 8}{\Delta t \times 10^6}$$
$$\text{Download Throughput (Mbps)} = \frac{\Delta B_{\text{recv}} \times 8}{\Delta t \times 10^6}$$

Similarly, for packet rates:

$$\text{Packets Sent/sec} = \frac{P_{\text{sent}}(t_2) - P_{\text{sent}}(t_1)}{\Delta t}$$

### Worked Numerical Example
* $t_1 = 100.0\text{ s}$, $B_{\text{recv}}(t_1) = 50,000,000\text{ bytes}$
* $t_2 = 101.0\text{ s}$, $B_{\text{recv}}(t_2) = 51,250,000\text{ bytes}$
* $\Delta t = 1.0\text{ s}$, $\Delta B_{\text{recv}} = 1,250,000\text{ bytes}$
* $\text{Download Rate} = \frac{1,250,000 \times 8}{1.0 \times 1,000,000} = \frac{10,000,000}{1,000,000} = \mathbf{10.0\text{ Mbps}}$

### Counter Reset & Register Rollover Handling
Hardware registers overflow at fixed capacities ($2^{32}-1$ for 32-bit counters, approximately 4.29 GB). Furthermore, if a network interface is reconnected or the machine reboots:

$$B_{\text{curr}} < B_{\text{prev}}$$

Without protection, $\Delta B$ becomes negative, yielding nonsensical negative rates (e.g., $-340\text{ Mbps}$).  
**NetworkAI Solution:** The collector checks:
$$\text{if } B_{\text{curr}} < B_{\text{prev}} \implies \text{Reset Baseline to } B_{\text{curr}}, \quad \text{Rate} = 0.0\text{ Mbps}$$

---

## 2. Feature Engineering Pipeline

Machine learning models require structured feature vectors. `NetworkFeatureExtractor` transforms raw metrics into a **15-dimensional numerical space** using a rolling window of size $W = 30$:

| Index | Feature Identifier | Mathematical Definition | Purpose |
| :---: | :--- | :--- | :--- |
| **0** | `download_mbps` | Instantaneous download rate | Measures inbound volume |
| **1** | `upload_mbps` | Instantaneous upload rate | Measures outbound volume |
| **2** | `total_mbps` | $\text{download} + \text{upload}$ | Measures combined link load |
| **3** | `packets_recv_per_sec` | Inbound packets per second | Measures packet frequency |
| **4** | `packets_sent_per_sec` | Outbound packets per second | Measures packet frequency |
| **5** | `total_packets_per_sec` | $\text{pkts}_{\text{recv}} + \text{pkts}_{\text{sent}}$ | Identifies packet flooding |
| **6** | `upload_download_ratio` | $\frac{\text{upload} + 0.01}{\text{download} + 0.01}$ | Detects exfiltration inversions |
| **7** | `packet_ratio` | $\frac{\text{pkts}_{\text{sent}} + 1.0}{\text{pkts}_{\text{recv}} + 1.0}$ | Detects directional asymmetry |
| **8** | `bytes_per_packet` | $\frac{\text{Total Bytes Transferred}}{\text{Total Packets}}$ | Distinguishes small scan packets from bulk data |
| **9** | `rolling_mean_mbps` | $\mu_{\text{mbps}} = \frac{1}{W} \sum_{i=1}^W \text{mbps}_i$ | Baseline average throughput |
| **10** | `rolling_std_mbps` | $\sigma_{\text{mbps}} = \sqrt{\frac{1}{W} \sum (\text{mbps}_i - \mu)^2}$ | Baseline throughput variance |
| **11** | `mbps_deviation` | $Z_{\text{mbps}} = \frac{|\text{mbps} - \mu|}{\sigma + 10^{-4}}$ | Normalized z-score deviation |
| **12** | `rolling_mean_packets` | $\mu_{\text{pkts}} = \frac{1}{W} \sum_{i=1}^W \text{pkts}_i$ | Baseline average packet rate |
| **13** | `rolling_std_packets` | $\sigma_{\text{pkts}} = \sqrt{\frac{1}{W} \sum (\text{pkts}_i - \mu)^2}$ | Baseline packet variance |
| **14** | `packets_deviation` | $Z_{\text{pkts}} = \frac{|\text{pkts} - \mu|}{\sigma + 10^{-4}}$ | Normalized packet z-score |

---

## 3. Unsupervised Anomaly Detection: Isolation Forest

### Theoretical Foundations
Traditional anomaly detection attempts to build a profile of "normal" data and flags points that fall outside the boundary. **Isolation Forest** (Liu, Ting, and Zhou) inverts this approach: it explicitly isolates anomalous points.

Because anomalies are "few and different," they require **fewer random recursive splits** to isolate in a binary tree compared to normal points that cluster densely.

```
       Normal Points (Dense Cluster)               Anomaly (Isolated Outlier)
          * * * * *                                            #
         * * * * * *                                (Isolated in 2 splits!)
          * * * * *
    (Requires many splits)
```

### Hyperparameter Configuration in NetworkAI
* **Number of Trees (`n_estimators`):** `100` (provides high stability without latency penalties).
* **Contamination Rate (`contamination`):** `0.05` ($5\%$ expected outlier density in baseline).
* **Warm-up Calibration Period:** `20 samples` (defers inference until baseline forms).
* **Training Buffer Size:** `500 samples` (sliding window of historical vectors).
* **Random Seed:** Fixed to `42` for strict determinism and academic reproducibility.

### Monotonic Anomaly Score Transformation
scikit-learn's `decision_function(X)` outputs the signed distance to the separating hyperplane:
* Positive values represent typical inliers.
* Negative values represent anomalous outliers.

To provide an intuitive, human-understandable index, NetworkAI maps the raw decision distance $d$ into a bounded $[0.00, 1.00]$ score using a steep, monotonic sigmoid:

$$\text{Raw Score} = \frac{1}{1 + e^{12 \times \text{clamp}(d, -5.0, 5.0)}}$$

$$\text{Anomaly Score} = \text{round}(\max(0.0, \min(1.0, \text{Raw Score})), 4)$$

```
 Decision Distance (d)   |   Transformed Anomaly Score   |   Assigned Severity
---------------------------------------------------------------------------------
  +0.25 (Steady Inlier)   |             0.047             |   Normal
   0.00 (Decision Margin) |             0.500             |   Normal
  -0.05 (Minor Deviation) |             0.645             |   Unusual Traffic
  -0.15 (Severe Outlier)  |             0.858             |   High Anomaly
```

### Score Severity Thresholds
* **Normal Traffic:** $\text{Score} < 0.60$
* **Unusual Traffic:** $0.60 \le \text{Score} < 0.80$
* **High Anomaly:** $\text{Score} \ge 0.80$

> **Critical Safety Disclaimer:**  
> An anomaly score is a measure of statistical divergence from recent baseline samples. **An anomaly score is NOT a probability of a cyberattack.** High throughput during an authorized software update or video stream will generate an elevated anomaly score; it does not indicate malicious activity.

---

## 4. Deterministic Statistical Fallback

If the model is warming up or the training buffer contains zero variance (e.g., an idle network adapter with all zeros), the system invokes a deterministic heuristic based on standard deviation multipliers:

$$\text{Significant Traffic Condition} = (\text{Total Mbps} > 2.0) \lor (\text{Total Packets/sec} > 100.0)$$

* If condition holds and either $Z_{\text{mbps}} \ge 4.5$ or $Z_{\text{pkts}} \ge 4.5 \implies \text{Score} = 0.85$ (`High Anomaly`).
* If condition holds and either $Z_{\text{mbps}} \ge 3.0$ or $Z_{\text{pkts}} \ge 3.0 \implies \text{Score} = 0.68$ (`Unusual Traffic`).
* Otherwise $\implies \text{Score} = 0.15$ (`Normal`).

---

## 5. Statistical Evaluation Metrics (Simulation Lab)

In the Simulation Lab, synthetic samples have known ground-truth labels ($y \in \{0, 1\}$) and model predictions ($\hat{y} \in \{0, 1\}$).

### Confusion Matrix Definitions
* **True Positives (TP):** Synthetically injected anomaly correctly classified as Unusual/High.
* **False Positives (FP):** Normal traffic incorrectly classified as an anomaly.
* **True Negatives (TN):** Normal baseline correctly classified as Normal.
* **False Negatives (FN):** Synthetically injected anomaly missed by the model.

### Metric Equations & Undefined Handling
$$\text{Accuracy} = \frac{TP + TN}{TP + TN + FP + FN}$$

$$\text{Precision} = \begin{cases} \frac{TP}{TP + FP} & \text{if } TP + FP > 0 \\ \text{None (Undefined)} & \text{if } TP + FP = 0 \end{cases}$$

$$\text{Recall} = \begin{cases} \frac{TP}{TP + FN} & \text{if } TP + FN > 0 \\ \text{None (Undefined)} & \text{if } TP + FN = 0 \end{cases}$$

$$F_1\text{-Score} = \begin{cases} 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}} & \text{if } \text{Precision} + \text{Recall} > 0 \\ \text{None (Undefined)} & \text{otherwise} \end{cases}$$

---

## 6. Topology Deduplication Algorithm

To prevent alert flooding when an interface condition persists across multiple polling cycles, `TopologyAlertService` applies stateful composite deduplication.

### Composite Deduplication Key
$$\text{Key} = (\text{source\_device\_id}, \text{event\_type}, \text{local\_interface}, \text{remote\_chassis\_id}, \text{is\_mock})$$

### Deduplication Logic
```python
query = db.query(TopologyAlertModel).filter(
    TopologyAlertModel.source_device_id == source_device_id,
    TopologyAlertModel.event_type == event_type,
    TopologyAlertModel.status.in_(["open", "acknowledged"]),
    TopologyAlertModel.is_mock == is_mock,
    TopologyAlertModel.local_interface == local_interface,
    TopologyAlertModel.remote_chassis_id == remote_chassis_id,
)
existing = query.first()

if existing:
    existing.occurrence_count += 1
    existing.last_seen_at = now
    existing.message = message
    db.commit()
    return existing
else:
    new_alert = TopologyAlertModel(...)
    db.add(new_alert)
    db.commit()
    return new_alert
```

This guarantees:
1. Active conditions increment their counter rather than inserting redundant rows.
2. Acknowledged alerts retain their acknowledged state without reverting to open.
3. Historical resolved alerts are preserved as permanent audit records.
