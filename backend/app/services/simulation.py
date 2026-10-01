"""Controlled Network Telemetry Simulation and Model Validation Engine.

Provides an isolated environment for evaluating the AI Anomaly Detection pipeline
against labeled, reproducible synthetic network scenarios without generating actual
host network traffic, packet flooding, or modifying real network interfaces.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.services.anomaly import AnomalyDetector, AnomalyEvaluationResult

logger = logging.getLogger("network_monitoring.simulation")

DISCLAIMER_TEXT = (
    "These validation metrics reflect controlled application-level synthetic simulation scenarios "
    "only. They do not constitute benchmarked or certified real-world cyberattack, DDoS, or intrusion "
    "detection performance."
)


@dataclass
class SyntheticSample:
    """A single synthetic network telemetry observation with ground truth."""

    step: int
    timestamp: datetime
    interface: str
    download_mbps: float
    upload_mbps: float
    packets_received_per_sec: float
    packets_sent_per_sec: float
    cumulative_bytes_sent: int
    cumulative_bytes_recv: int
    session_transferred_mb: float
    is_initial_sample: bool
    ground_truth_anomaly: bool
    expected_severity: str  # 'Normal', 'Unusual Traffic', 'High Anomaly'
    expected_behavior: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert sample to dict compatible with NetworkFeatureExtractor."""
        return {
            "step": self.step,
            "timestamp": self.timestamp,
            "interface": self.interface,
            "download_mbps": self.download_mbps,
            "upload_mbps": self.upload_mbps,
            "packets_received_per_sec": self.packets_received_per_sec,
            "packets_recv_per_sec": self.packets_received_per_sec,
            "packets_sent_per_sec": self.packets_sent_per_sec,
            "cumulative_bytes_sent": self.cumulative_bytes_sent,
            "cumulative_bytes_recv": self.cumulative_bytes_recv,
            "session_transferred_mb": self.session_transferred_mb,
            "is_initial_sample": self.is_initial_sample,
            "ground_truth_anomaly": self.ground_truth_anomaly,
            "expected_severity": self.expected_severity,
        }


@dataclass
class ScenarioDefinition:
    """Definition and metadata for a controlled simulation scenario."""

    scenario_id: str
    name: str
    category: str
    description: str
    duration_seconds: int
    expected_behavior: str


@dataclass
class ConfusionMatrix:
    """Confusion matrix results for binary anomaly classification."""

    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    total_samples: int

    def to_dict(self) -> Dict[str, int]:
        return {
            "true_positives": self.true_positives,
            "true_negatives": self.true_negatives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "total_samples": self.total_samples,
        }


@dataclass
class ValidationMetrics:
    """Standard statistical validation metrics with proper mathematical undefined handling."""

    precision: Optional[float]
    recall: Optional[float]
    f1_score: Optional[float]
    accuracy: float
    detection_latency_seconds: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "precision": round(self.precision, 4) if self.precision is not None else None,
            "recall": round(self.recall, 4) if self.recall is not None else None,
            "f1_score": round(self.f1_score, 4) if self.f1_score is not None else None,
            "accuracy": round(self.accuracy, 4),
            "detection_latency_seconds": (
                round(self.detection_latency_seconds, 2)
                if self.detection_latency_seconds is not None
                else None
            ),
        }


@dataclass
class SimulationTimelinePoint:
    """Recorded observation at a single time step in the simulation."""

    step: int
    timestamp: datetime
    download_mbps: float
    upload_mbps: float
    packets_per_sec: float
    ground_truth_anomaly: bool
    expected_severity: str
    predicted_score: float
    predicted_severity: str
    is_detected: bool
    detection_method: str
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "timestamp": self.timestamp.isoformat(),
            "download_mbps": round(self.download_mbps, 4),
            "upload_mbps": round(self.upload_mbps, 4),
            "packets_per_sec": round(self.packets_per_sec, 2),
            "ground_truth_anomaly": self.ground_truth_anomaly,
            "expected_severity": self.expected_severity,
            "predicted_score": round(self.predicted_score, 4),
            "predicted_severity": self.predicted_severity,
            "is_detected": self.is_detected,
            "detection_method": self.detection_method,
            "explanation": self.explanation,
        }


@dataclass
class SimulationResult:
    """Comprehensive validation result output for a simulation run."""

    scenario_id: str
    scenario_name: str
    category: str
    description: str
    seed: int
    duration_seconds: int
    evaluated_at: datetime
    confusion_matrix: ConfusionMatrix
    metrics: ValidationMetrics
    timeline: List[SimulationTimelinePoint]
    expected_behavior: str
    disclaimer: str = DISCLAIMER_TEXT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "category": self.category,
            "description": self.description,
            "seed": self.seed,
            "duration_seconds": self.duration_seconds,
            "evaluated_at": self.evaluated_at.isoformat(),
            "confusion_matrix": self.confusion_matrix.to_dict(),
            "metrics": self.metrics.to_dict(),
            "timeline": [p.to_dict() for p in self.timeline],
            "expected_behavior": self.expected_behavior,
            "disclaimer": self.disclaimer,
        }


class SimulationService:
    """Manages synthetic scenario generation and isolated model validation."""

    SIM_INTERFACE = "sim0"
    WARMUP_STEPS = 31  # Step 1 is initial calibration tick, steps 2..31 provide 30 baseline samples

    SCENARIOS: Dict[str, ScenarioDefinition] = {
        "normal_stable": ScenarioDefinition(
            scenario_id="normal_stable",
            name="Normal Stable Traffic",
            category="Baseline",
            description=(
                "Simulates steady, non-bursty office browsing and streaming traffic. "
                "Maintains consistent download (6-12 Mbps) and upload (1-3 Mbps) rates."
            ),
            duration_seconds=50,
            expected_behavior=(
                "All samples must be classified as Normal with low anomaly scores (< 0.40). "
                "Zero false alarms expected."
            ),
        ),
        "gradual_increase": ScenarioDefinition(
            scenario_id="gradual_increase",
            name="Gradual Throughput Increase",
            category="Trend Drift",
            description=(
                "Evaluates model adaptation to routine workload growth. Following baseline calibration, "
                "throughput ramps smoothly from 8.5 Mbps to 22 Mbps over 19 seconds."
            ),
            duration_seconds=50,
            expected_behavior=(
                "Rolling statistical windows adapt to gradual drift. Traffic remains classified as Normal "
                "or minor transient score drift, verifying resilience against false alarms on steady growth."
            ),
        ),
        "sudden_download_spike": ScenarioDefinition(
            scenario_id="sudden_download_spike",
            name="Sudden Download Spike",
            category="Throughput Anomaly",
            description=(
                "Simulates a massive unpredicted inbound burst (e.g., large unauthorized download "
                "or traffic surge). Inbound throughput jumps instantly from 8.5 Mbps to 140 Mbps."
            ),
            duration_seconds=60,
            expected_behavior=(
                "Rapid detection at onset step with sustained anomaly score >= 0.60. "
                "Immediate self-clearing when burst subsides back to baseline."
            ),
        ),
        "sudden_upload_spike": ScenarioDefinition(
            scenario_id="sudden_upload_spike",
            name="Sudden Upload Spike (Exfiltration Pattern)",
            category="Ratio Anomaly",
            description=(
                "Simulates an unexpected high-volume outbound burst (e.g., data exfiltration or rogue backup). "
                "Outbound throughput surges from 2.0 Mbps to 85 Mbps, sharply inverting the upload/download ratio."
            ),
            duration_seconds=60,
            expected_behavior=(
                "Immediate anomaly classification due to simultaneous rate deviation and ratio inversion."
            ),
        ),
        "unusual_packet_rate": ScenarioDefinition(
            scenario_id="unusual_packet_rate",
            name="Unusual Packet-Rate Increase (Scan Pattern)",
            category="Packet Rate Anomaly",
            description=(
                "Simulates a flood of small packets (e.g., high-speed port scan or SYN flood signature). "
                "Packet rate jumps to 19,000 pkts/sec while payload volume remains small (under 2 Mbps), "
                "collapsing average bytes-per-packet."
            ),
            duration_seconds=60,
            expected_behavior=(
                "Detector identifies abnormal packet rate and depressed bytes-per-packet structural deviation."
            ),
        ),
        "bidirectional_burst": ScenarioDefinition(
            scenario_id="bidirectional_burst",
            name="Bidirectional Traffic Burst",
            category="Throughput Anomaly",
            description=(
                "Simulates simultaneous severe download (110 Mbps) and upload (75 Mbps) spikes with "
                "elevated packet exchange across both transmission directions."
            ),
            duration_seconds=60,
            expected_behavior=(
                "Sustained High Anomaly classification across all active burst steps."
            ),
        ),
        "return_to_baseline": ScenarioDefinition(
            scenario_id="return_to_baseline",
            name="Return to Normal Baseline",
            category="Recovery",
            description=(
                "Evaluates detector recovery dynamics. Following an 11-second high-intensity spike, "
                "traffic returns to baseline and remains steady for 18 seconds."
            ),
            duration_seconds=60,
            expected_behavior=(
                "Anomaly scores decline back below the 0.60 threshold as rolling statistics normalize, "
                "verifying system self-clearing without manual intervention."
            ),
        ),
    }

    def __init__(self) -> None:
        self._latest_result: Optional[SimulationResult] = None

    def list_scenarios(self) -> List[Dict[str, Any]]:
        """Return list of all registered simulation scenario definitions."""
        return [
            {
                "scenario_id": s.scenario_id,
                "name": s.name,
                "category": s.category,
                "description": s.description,
                "duration_seconds": s.duration_seconds,
                "expected_behavior": s.expected_behavior,
            }
            for s in self.SCENARIOS.values()
        ]

    def get_scenario(self, scenario_id: str) -> Optional[ScenarioDefinition]:
        """Fetch definition for a specific scenario ID."""
        return self.SCENARIOS.get(scenario_id)

    def generate_scenario_samples(
        self,
        scenario_id: str,
        seed: int = 42,
    ) -> List[SyntheticSample]:
        """Generate deterministic, labeled synthetic metric sequence for a given scenario."""
        if scenario_id not in self.SCENARIOS:
            raise ValueError(f"Unknown scenario ID: '{scenario_id}'")

        definition = self.SCENARIOS[scenario_id]
        rng = np.random.default_rng(seed)
        base_time = datetime.now(timezone.utc) - timedelta(seconds=definition.duration_seconds)

        samples: List[SyntheticSample] = []
        cum_sent = 100 * 1024 * 1024
        cum_recv = 400 * 1024 * 1024
        session_mb = 0.0

        for step in range(1, definition.duration_seconds + 1):
            ts = base_time + timedelta(seconds=step)
            is_initial = (step == 1)

            # Generate synthetic metrics based on scenario parameters
            dl, ul, rx_pkts, tx_pkts, is_anomaly, expected_sev = self._compute_step_telemetry(
                scenario_id=scenario_id,
                step=step,
                rng=rng,
            )

            # Update realistic cumulative counters
            cum_recv += int(dl * (1024 * 1024 / 8))
            cum_sent += int(ul * (1024 * 1024 / 8))
            session_mb += (dl + ul) / 8.0

            sample = SyntheticSample(
                step=step,
                timestamp=ts,
                interface=self.SIM_INTERFACE,
                download_mbps=max(0.0, float(dl)),
                upload_mbps=max(0.0, float(ul)),
                packets_received_per_sec=max(0.0, float(rx_pkts)),
                packets_sent_per_sec=max(0.0, float(tx_pkts)),
                cumulative_bytes_sent=cum_sent,
                cumulative_bytes_recv=cum_recv,
                session_transferred_mb=round(session_mb, 3),
                is_initial_sample=is_initial,
                ground_truth_anomaly=is_anomaly,
                expected_severity=expected_sev,
                expected_behavior=definition.expected_behavior,
            )
            samples.append(sample)

        return samples

    def _compute_step_telemetry(
        self,
        scenario_id: str,
        step: int,
        rng: np.random.Generator,
    ) -> Tuple[float, float, float, float, bool, str]:
        """Compute synthetic metric values and ground-truth for a single step."""
        # Baseline traffic parameters (steps 1..31 warmup is always normal baseline)
        base_dl = 8.5 + float(rng.normal(0, 0.4))
        base_ul = 2.0 + float(rng.normal(0, 0.2))
        base_rx_pkts = 850 + float(rng.normal(0, 30))
        base_tx_pkts = 350 + float(rng.normal(0, 20))

        if scenario_id == "normal_stable":
            # Normal stable throughput across all steps
            return base_dl, base_ul, base_rx_pkts, base_tx_pkts, False, "Normal"

        elif scenario_id == "gradual_increase":
            # Steps 32..50 ramp throughput smoothly from 8.5 to 22 Mbps
            if step <= self.WARMUP_STEPS:
                return base_dl, base_ul, base_rx_pkts, base_tx_pkts, False, "Normal"
            factor = (step - self.WARMUP_STEPS) / 19.0  # 0.0 -> 1.0
            dl = base_dl + (13.5 * factor) + float(rng.normal(0, 0.3))
            ul = base_ul + (3.5 * factor) + float(rng.normal(0, 0.15))
            rx_pkts = base_rx_pkts + (800 * factor)
            tx_pkts = base_tx_pkts + (300 * factor)
            return dl, ul, rx_pkts, tx_pkts, False, "Normal"

        elif scenario_id == "sudden_download_spike":
            # Steps 32..42 experience 16x download burst with asymmetric ACK return
            if 32 <= step <= 42:
                dl = 140.0 + float(rng.normal(0, 3.0))
                ul = base_ul + float(rng.normal(0, 0.15))
                rx_pkts = 12000 + float(rng.normal(0, 200))
                tx_pkts = 350 + float(rng.normal(0, 10))
                return dl, ul, rx_pkts, tx_pkts, True, "High Anomaly"
            return base_dl, base_ul, base_rx_pkts, base_tx_pkts, False, "Normal"

        elif scenario_id == "sudden_upload_spike":
            # Steps 32..42 experience severe upload surge (exfiltration profile)
            if 32 <= step <= 42:
                dl = base_dl + float(rng.normal(0, 0.2))
                ul = 85.0 + float(rng.normal(0, 2.5))
                rx_pkts = 850 + float(rng.normal(0, 15))
                tx_pkts = 8500 + float(rng.normal(0, 150))
                return dl, ul, rx_pkts, tx_pkts, True, "High Anomaly"
            return base_dl, base_ul, base_rx_pkts, base_tx_pkts, False, "Normal"

        elif scenario_id == "unusual_packet_rate":
            # Steps 32..42 experience massive packet surge with tiny payload
            if 32 <= step <= 42:
                dl = 1.5 + float(rng.normal(0, 0.1))
                ul = 0.5 + float(rng.normal(0, 0.05))
                rx_pkts = 19000 + float(rng.normal(0, 300))
                tx_pkts = 500 + float(rng.normal(0, 20))
                return dl, ul, rx_pkts, tx_pkts, True, "High Anomaly"
            return base_dl, base_ul, base_rx_pkts, base_tx_pkts, False, "Normal"

        elif scenario_id == "bidirectional_burst":
            # Steps 32..42 concurrent bidirectional surge
            if 32 <= step <= 42:
                dl = 110.0 + float(rng.normal(0, 2.5))
                ul = 75.0 + float(rng.normal(0, 2.0))
                rx_pkts = 11000 + float(rng.normal(0, 200))
                tx_pkts = 7500 + float(rng.normal(0, 150))
                return dl, ul, rx_pkts, tx_pkts, True, "High Anomaly"
            return base_dl, base_ul, base_rx_pkts, base_tx_pkts, False, "Normal"

        elif scenario_id == "return_to_baseline":
            # Steps 32..42 burst, steps 43..60 return to normal baseline
            if 32 <= step <= 42:
                dl = 110.0 + float(rng.normal(0, 2.5))
                ul = 75.0 + float(rng.normal(0, 2.0))
                rx_pkts = 11000 + float(rng.normal(0, 200))
                tx_pkts = 7500 + float(rng.normal(0, 150))
                return dl, ul, rx_pkts, tx_pkts, True, "High Anomaly"
            return base_dl, base_ul, base_rx_pkts, base_tx_pkts, False, "Normal"

        # Fallback to baseline
        return base_dl, base_ul, base_rx_pkts, base_tx_pkts, False, "Normal"

    def run_simulation(
        self,
        scenario_id: str,
        seed: int = 42,
    ) -> SimulationResult:
        """Execute a controlled simulation against an isolated AnomalyDetector instance."""
        definition = self.get_scenario(scenario_id)
        if not definition:
            raise ValueError(f"Unknown scenario ID: '{scenario_id}'")

        # 1. Generate deterministic synthetic telemetry
        samples = self.generate_scenario_samples(scenario_id=scenario_id, seed=seed)

        # 2. Instantiate isolated AnomalyDetector with identical production architecture
        # Does NOT touch live monitoring_service or production SQLite database
        isolated_detector = AnomalyDetector(
            contamination=0.05,
            warmup_samples=30,
            min_train_samples=20,
            random_state=seed,
        )

        timeline_points: List[SimulationTimelinePoint] = []

        # 3. Stream synthetic samples through detector
        for sample in samples:
            sample_dict = sample.to_dict()
            eval_result: AnomalyEvaluationResult = isolated_detector.evaluate(sample_dict)

            # Auto-train once warmup baseline (30 samples) is accumulated, trimming early window startup points
            if isolated_detector.is_warmed_up and not isolated_detector.is_trained:
                training_data = list(isolated_detector._training_buffer)[5:]
                isolated_detector.train(training_data)

            is_detected = eval_result.is_anomaly or (eval_result.anomaly_score >= 0.60)

            timeline_points.append(
                SimulationTimelinePoint(
                    step=sample.step,
                    timestamp=sample.timestamp,
                    download_mbps=sample.download_mbps,
                    upload_mbps=sample.upload_mbps,
                    packets_per_sec=sample.packets_received_per_sec + sample.packets_sent_per_sec,
                    ground_truth_anomaly=sample.ground_truth_anomaly,
                    expected_severity=sample.expected_severity,
                    predicted_score=eval_result.anomaly_score,
                    predicted_severity=eval_result.severity,
                    is_detected=is_detected,
                    detection_method=eval_result.detection_method,
                    explanation=eval_result.explanation,
                )
            )

        # 4. Compute confusion matrix and validation metrics
        cm, metrics = self._calculate_validation_metrics(timeline_points)

        result = SimulationResult(
            scenario_id=definition.scenario_id,
            scenario_name=definition.name,
            category=definition.category,
            description=definition.description,
            seed=seed,
            duration_seconds=definition.duration_seconds,
            evaluated_at=datetime.now(timezone.utc),
            confusion_matrix=cm,
            metrics=metrics,
            timeline=timeline_points,
            expected_behavior=definition.expected_behavior,
            disclaimer=DISCLAIMER_TEXT,
        )

        self._latest_result = result
        f1_str = f"{metrics.f1_score:.2f}" if metrics.f1_score is not None else "undefined"
        logger.info(
            "Completed simulation for '%s' (seed=%d): Acc=%.2f, F1=%s, TP=%d, FP=%d, FN=%d, TN=%d",
            scenario_id,
            seed,
            metrics.accuracy,
            f1_str,
            cm.true_positives,
            cm.false_positives,
            cm.false_negatives,
            cm.true_negatives,
        )
        return result

    def _calculate_validation_metrics(
        self,
        timeline: List[SimulationTimelinePoint],
    ) -> Tuple[ConfusionMatrix, ValidationMetrics]:
        """Calculate TP, TN, FP, FN, Precision, Recall, F1, Accuracy, and Detection Latency.

        Safely and mathematically handles edge cases including scenarios with zero ground-truth anomalies
        (where precision/recall are undefined), zero positive model classifications, and unreached detections.
        """
        tp = sum(1 for p in timeline if p.is_detected and p.ground_truth_anomaly)
        tn = sum(1 for p in timeline if not p.is_detected and not p.ground_truth_anomaly)
        fp = sum(1 for p in timeline if p.is_detected and not p.ground_truth_anomaly)
        fn = sum(1 for p in timeline if not p.is_detected and p.ground_truth_anomaly)
        total = len(timeline)

        # Accuracy: (TP + TN) / Total
        accuracy = (tp + tn) / total if total > 0 else 0.0

        # Precision: TP / (TP + FP)
        # Undefined (None) when detector makes 0 positive alarms (TP + FP == 0)
        if (tp + fp) > 0:
            precision: Optional[float] = float(tp / (tp + fp))
        else:
            precision = None

        # Recall: TP / (TP + FN)
        # Undefined (None) when scenario contains 0 ground-truth anomalies (TP + FN == 0)
        if (tp + fn) > 0:
            recall: Optional[float] = float(tp / (tp + fn))
        else:
            recall = None

        # F1 Score: 2 * (P * R) / (P + R)
        # Undefined (None) if either precision or recall is undefined.
        # Evaluates to 0.0 if precision or recall is 0.0.
        if precision is not None and recall is not None:
            if (precision + recall) > 0.0:
                f1_score: Optional[float] = float(2.0 * (precision * recall) / (precision + recall))
            else:
                f1_score = 0.0
        else:
            f1_score = None

        # Detection Latency:
        # Time steps from the first ground truth anomaly onset until the first positive detection.
        # Each simulation step has a fixed 1.0 second time resolution.
        anomaly_onset_step: Optional[int] = None
        first_detected_step: Optional[int] = None

        for p in timeline:
            if p.ground_truth_anomaly and anomaly_onset_step is None:
                anomaly_onset_step = p.step
            if anomaly_onset_step is not None and p.is_detected and first_detected_step is None:
                first_detected_step = p.step

        if anomaly_onset_step is not None:
            if first_detected_step is not None:
                # Latency in seconds (step difference: 0.0s = immediate onset detection)
                latency: Optional[float] = float(max(0, first_detected_step - anomaly_onset_step))
            else:
                # Anomaly occurred but was never detected by the detector (unreached detection)
                latency = None
        else:
            # No ground-truth anomaly occurred in this scenario (e.g. normal baseline)
            latency = None

        cm = ConfusionMatrix(
            true_positives=tp,
            true_negatives=tn,
            false_positives=fp,
            false_negatives=fn,
            total_samples=total,
        )
        metrics = ValidationMetrics(
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            accuracy=accuracy,
            detection_latency_seconds=latency,
        )
        return cm, metrics

    def get_latest_result(self) -> Optional[SimulationResult]:
        """Retrieve most recently executed simulation result."""
        return self._latest_result

    def reset(self) -> None:
        """Clear cached simulation results."""
        self._latest_result = None
        logger.info("Simulation service state reset.")


# Singleton service instance
simulation_service = SimulationService()
