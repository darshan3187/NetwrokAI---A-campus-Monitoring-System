"""Isolation Forest anomaly detection engine for network telemetry observability.

Analyzes multi-dimensional network feature vectors to detect statistical and structural
outliers. Employs scikit-learn's Isolation Forest with a configurable contamination rate,
a warm-up calibration phase, and deterministic statistical fallbacks.
"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import math
from typing import Deque, Dict, List, Optional, Tuple, Union
import numpy as np
from sklearn.ensemble import IsolationForest

from app.collector import NetworkMetrics
from app.services.features import NetworkFeatureExtractor, NetworkFeatures

logger = logging.getLogger("network_monitoring.anomaly")


@dataclass
class AnomalyEvaluationResult:
    """Standardized output of the anomaly evaluation pipeline."""

    timestamp: datetime
    interface: str
    anomaly_score: float  # Normalized 0.0 to 1.0
    severity: str         # 'Normal', 'Unusual Traffic', 'High Anomaly'
    is_anomaly: bool      # True if severity != 'Normal'
    detection_method: str # 'isolation_forest', 'statistical_fallback', 'warmup'
    explanation: str      # Human-readable descriptive diagnostic
    metrics_snapshot: Dict[str, float]
    features_vector: List[float]


class AnomalyDetector:
    """Manages feature extraction, model calibration, and live anomaly evaluation."""

    # Severity classifications
    SEVERITY_NORMAL = "Normal"
    SEVERITY_UNUSUAL = "Unusual Traffic"
    SEVERITY_HIGH = "High Anomaly"

    # Score thresholds
    THRESHOLD_UNUSUAL = 0.60
    THRESHOLD_HIGH = 0.80

    def __init__(
        self,
        contamination: float = 0.05,
        warmup_samples: int = 20,
        min_train_samples: int = 20,
        max_buffer_samples: int = 500,
        random_state: int = 42,
    ) -> None:
        self.contamination = contamination
        self.warmup_samples = warmup_samples
        self.min_train_samples = min_train_samples
        self.max_buffer_samples = max_buffer_samples
        self.random_state = random_state

        self.feature_extractor = NetworkFeatureExtractor(window_size=30)
        self._training_buffer: Deque[List[float]] = deque(maxlen=max_buffer_samples)

        self._model: Optional[IsolationForest] = None
        self._is_trained = False
        self._samples_observed = 0
        self._last_trained_sample_count = 0
        self.active_interface: Optional[str] = None

    def reset(self, interface: Optional[str] = None) -> None:
        """Reset internal state when switching network adapters or restarting session."""
        self.feature_extractor.reset(interface)
        self._training_buffer.clear()
        self._model = None
        self._is_trained = False
        self._samples_observed = 0
        self._last_trained_sample_count = 0
        self.active_interface = interface
        logger.info("Anomaly detector reset for interface '%s'", interface)

    @property
    def is_warmed_up(self) -> bool:
        """Whether sufficient baseline samples have been collected."""
        return self._samples_observed >= self.warmup_samples

    @property
    def is_trained(self) -> bool:
        """Whether an Isolation Forest model is active and trained."""
        return self._is_trained and self._model is not None

    @property
    def status(self) -> str:
        """Operational status of the detector ('trained', 'warming_up', 'ready_to_train')."""
        if self._is_trained:
            return "active"
        if not self.is_warmed_up:
            return "warming_up"
        return "ready_to_train"

    def train(self, sample_vectors: Optional[List[List[float]]] = None) -> bool:
        """Fit the Isolation Forest model on collected or provided feature vectors.

        Ensures reproducibility with a fixed random_state and applies variance checks
        to prevent fitting on completely identical zero-variance data.
        """
        training_data = sample_vectors or list(self._training_buffer)
        if len(training_data) < self.min_train_samples:
            logger.debug(
                "Insufficient samples to train Isolation Forest (%d / %d required)",
                len(training_data),
                self.min_train_samples,
            )
            return False

        X = np.array(training_data, dtype=np.float32)

        # Handle zero-variance degenerate case (e.g. idle adapter with all 0s)
        # Add minimal jitter to prevent singular matrix/degenerate splits in trees
        variances = np.var(X, axis=0)
        if np.all(variances < 1e-6):
            logger.debug("Feature buffer has near-zero variance; applying slight regularization")
            X = X + np.random.RandomState(self.random_state).normal(0.0, 1e-4, size=X.shape)

        try:
            model = IsolationForest(
                n_estimators=100,
                contamination=self.contamination,
                random_state=self.random_state,
                n_jobs=1,  # Keep deterministic and single-threaded for stability
            )
            model.fit(X)
            self._model = model
            self._is_trained = True
            self._last_trained_sample_count = self._samples_observed
            logger.info(
                "Successfully trained Isolation Forest on %d samples (contamination=%.3f)",
                len(training_data),
                self.contamination,
            )
            return True
        except Exception as exc:
            logger.exception("Failed to train Isolation Forest model: %s", exc)
            return False

    def evaluate(
        self,
        sample: Union[NetworkMetrics, dict, object],
    ) -> AnomalyEvaluationResult:
        """Evaluate a new network telemetry sample through the anomaly pipeline.

        Extracts features, records training data, evaluates via Isolation Forest or fallback,
        and generates an objective human-readable explanation.
        """
        features = self.feature_extractor.extract(sample)

        # Determine timestamp and interface
        if isinstance(sample, dict):
            timestamp_val = sample.get("timestamp", datetime.now(timezone.utc))
            iface = str(sample.get("interface", sample.get("interface_name", "unknown")))
            is_initial = bool(sample.get("is_initial_sample", False))
        else:
            ts = getattr(sample, "timestamp", None)
            if isinstance(ts, (int, float)):
                timestamp_val = datetime.fromtimestamp(ts, tz=timezone.utc)
            elif isinstance(ts, datetime):
                timestamp_val = ts
            else:
                timestamp_val = datetime.now(timezone.utc)
            iface = getattr(sample, "interface_name", getattr(sample, "interface", "unknown"))
            is_initial = bool(getattr(sample, "is_initial_sample", False))

        # Check interface switch
        if self.active_interface is not None and iface != self.active_interface:
            self.reset(iface)
        elif self.active_interface is None:
            self.active_interface = iface

        # Baseline / initial calibration tick handling
        if is_initial:
            return AnomalyEvaluationResult(
                timestamp=timestamp_val,
                interface=iface,
                anomaly_score=0.0,
                severity=self.SEVERITY_NORMAL,
                is_anomaly=False,
                detection_method="initial_baseline",
                explanation="Initial baseline calibration sample; rates not evaluated.",
                metrics_snapshot=features.to_dict(),
                features_vector=features.to_vector(),
            )

        # Register observation
        self._samples_observed += 1
        vec = features.to_vector()
        self._training_buffer.append(vec)

        # Phase A: Warm-up period check
        if not self.is_warmed_up:
            return AnomalyEvaluationResult(
                timestamp=timestamp_val,
                interface=iface,
                anomaly_score=0.0,
                severity=self.SEVERITY_NORMAL,
                is_anomaly=False,
                detection_method="warmup",
                explanation=(
                    f"Baseline calibration phase ({self._samples_observed}/{self.warmup_samples} samples collected); "
                    "alerts deferred until baseline is established."
                ),
                metrics_snapshot=features.to_dict(),
                features_vector=vec,
            )

        # Phase B: Isolation Forest evaluation if trained
        if self.is_trained and self._model is not None:
            score, severity, explanation = self._evaluate_with_model(features)
            return AnomalyEvaluationResult(
                timestamp=timestamp_val,
                interface=iface,
                anomaly_score=score,
                severity=severity,
                is_anomaly=(severity != self.SEVERITY_NORMAL),
                detection_method="isolation_forest",
                explanation=explanation,
                metrics_snapshot=features.to_dict(),
                features_vector=vec,
            )

        # Phase C: Deterministic statistical fallback if model is not yet fitted
        score, severity, explanation = self._evaluate_with_statistical_fallback(features)
        return AnomalyEvaluationResult(
            timestamp=timestamp_val,
            interface=iface,
            anomaly_score=score,
            severity=severity,
            is_anomaly=(severity != self.SEVERITY_NORMAL),
            detection_method="statistical_fallback",
            explanation=explanation,
            metrics_snapshot=features.to_dict(),
            features_vector=vec,
        )

    def _evaluate_with_model(
        self, features: NetworkFeatures
    ) -> Tuple[float, str, str]:
        """Inference with trained Isolation Forest model."""
        assert self._model is not None

        X = features.to_numpy()
        # decision_function gives signed distance to separating hyperplane:
        # positive = inlier, negative = outlier
        decision = float(self._model.decision_function(X)[0])

        # Smooth, monotonic mapping from decision to [0.0, 1.0] score:
        # S = 1 / (1 + exp(12 * decision))
        # d = 0.25 (typical steady state inlier) -> score ~ 0.047
        # d = 0.00 (model decision boundary) -> score = 0.50
        # d = -0.05 (unusual outlier) -> score ~ 0.64
        # d = -0.15 (strong outlier) -> score ~ 0.85
        try:
            # Prevent overflow in exp
            clamped_decision = max(-5.0, min(5.0, decision))
            raw_score = 1.0 / (1.0 + math.exp(12.0 * clamped_decision))
        except OverflowError:
            raw_score = 1.0 if decision < 0 else 0.0

        normalized_score = round(max(0.0, min(1.0, raw_score)), 4)

        # Determine severity category
        if normalized_score >= self.THRESHOLD_HIGH:
            severity = self.SEVERITY_HIGH
        elif normalized_score >= self.THRESHOLD_UNUSUAL:
            severity = self.SEVERITY_UNUSUAL
        else:
            severity = self.SEVERITY_NORMAL

        explanation = self._generate_explanation(features, severity, normalized_score)
        return normalized_score, severity, explanation

    def _evaluate_with_statistical_fallback(
        self, features: NetworkFeatures
    ) -> Tuple[float, str, str]:
        """Deterministic statistical heuristic when training buffer is accumulating or model is unfitted."""
        # Use throughput and packet rate z-score deviations
        mbps_dev = features.mbps_deviation
        pkts_dev = features.packets_deviation

        # Require a non-trivial absolute volume before flagging to avoid low-bandwidth noise
        is_significant_traffic = (features.total_mbps > 2.0) or (features.total_packets_per_sec > 100.0)

        if is_significant_traffic and (mbps_dev >= 4.5 or pkts_dev >= 4.5):
            score = 0.85
            severity = self.SEVERITY_HIGH
        elif is_significant_traffic and (mbps_dev >= 3.0 or pkts_dev >= 3.0):
            score = 0.68
            severity = self.SEVERITY_UNUSUAL
        else:
            score = round(min(0.35, max(0.02, mbps_dev * 0.05)), 4)
            severity = self.SEVERITY_NORMAL

        explanation = self._generate_explanation(features, severity, score, fallback=True)
        return score, severity, explanation

    def _generate_explanation(
        self,
        f: NetworkFeatures,
        severity: str,
        score: float,
        fallback: bool = False,
    ) -> str:
        """Synthesize an objective, descriptive explanation of traffic conditions.

        Does not assert unverified attack identities like DDoS or malware;
        focuses strictly on observable throughput, packet rates, and baseline variance.
        """
        if severity == self.SEVERITY_NORMAL:
            return "Traffic throughput and packet rates within established baseline parameters."

        suffix = " (Statistical baseline evaluation)" if fallback else ""

        # Identify primary contributing anomalies
        reasons = []

        if f.download_mbps > 5.0 and f.mbps_deviation >= 3.0:
            reasons.append(
                f"Download throughput surge to {f.download_mbps:.2f} Mbps "
                f"({f.mbps_deviation:.1f}x standard deviation from {f.rolling_mean_mbps:.2f} Mbps rolling baseline)"
            )
        elif f.upload_mbps > 5.0 and f.mbps_deviation >= 3.0:
            reasons.append(
                f"Upload throughput surge to {f.upload_mbps:.2f} Mbps "
                f"({f.mbps_deviation:.1f}x standard deviation from {f.rolling_mean_mbps:.2f} Mbps rolling baseline)"
            )
        elif f.mbps_deviation >= 3.0:
            reasons.append(
                f"Total traffic rate {f.total_mbps:.2f} Mbps deviates significantly ({f.mbps_deviation:.1f} std dev) from rolling mean"
            )

        if f.packet_ratio >= 15.0 and f.packets_sent_per_sec > 50.0:
            reasons.append(
                f"Asymmetric outbound packet ratio ({f.packet_ratio:.1f}:1 send-to-receive)"
            )
        elif f.packet_ratio <= 0.05 and f.packets_recv_per_sec > 50.0:
            reasons.append(
                f"Asymmetric inbound packet ratio ({f.packets_recv_per_sec / (f.packets_sent_per_sec + 0.01):.1f}:1 receive-to-send)"
            )

        if f.packets_deviation >= 3.5:
            reasons.append(
                f"Packet transmission frequency ({f.total_packets_per_sec:.0f} pkts/s) elevated {f.packets_deviation:.1f} std dev above baseline"
            )

        if not reasons:
            reasons.append(
                f"Multi-feature correlation anomaly detected (score={score:.2f}, baseline mean={f.rolling_mean_mbps:.2f} Mbps)"
            )

        return f"{severity}: {'; '.join(reasons)}.{suffix}"
