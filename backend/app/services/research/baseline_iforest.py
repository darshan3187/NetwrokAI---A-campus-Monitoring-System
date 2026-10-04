"""Isolation Forest baseline engine for comparative network flow evaluation.

Provides a standardized baseline comparison against the proposed River One-Class SVM.
Trained on the exact same benign warm-up flows and evaluated on the exact same test flows.
Clearly distinguishes between batch/offline tree ensemble learning (Isolation Forest)
and dynamic stream learning (River Online OCSVM).
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional
import numpy as np
from sklearn.ensemble import IsolationForest

logger = logging.getLogger("network_monitoring.research.iforest")

FEATURE_KEYS = [
    "IPV4_SRC_ADDR",
    "IPV4_DST_ADDR",
    "L4_SRC_PORT",
    "L4_DST_PORT",
    "PROTOCOL",
    "IN_BYTES",
    "OUT_BYTES",
    "FLOW_DURATION_MILLISECONDS",
]


class BaselineIsolationForest:
    """Manages Isolation Forest baseline training and flow evaluation."""

    def __init__(
        self,
        contamination: float = 0.05,
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> None:
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.model: Optional[IsolationForest] = None
        self.warmup_duration_sec = 0.0

    def flows_to_array(self, flows: List[Dict[str, float]]) -> np.ndarray:
        """Convert list of flow dictionaries to NumPy 2D array."""
        arr = np.zeros((len(flows), len(FEATURE_KEYS)), dtype=np.float32)
        for i, f in enumerate(flows):
            for j, k in enumerate(FEATURE_KEYS):
                arr[i, j] = f.get(k, 0.0)
        return arr

    def train_baseline(
        self,
        warmup_flows: List[Dict[str, float]],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> float:
        """Train Isolation Forest on the benign baseline flows."""
        t0 = time.perf_counter()
        X = self.flows_to_array(warmup_flows)

        # Apply minor variance check to avoid zero-division in degenerate idle sets
        variances = np.var(X, axis=0)
        if np.all(variances < 1e-6):
            rng = np.random.RandomState(self.random_state)
            X = X + rng.normal(0.0, 1e-4, size=X.shape)

        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=self.random_state,
            n_jobs=1,
        )
        self.model.fit(X)

        elapsed = time.perf_counter() - t0
        self.warmup_duration_sec = elapsed

        if progress_callback:
            progress_callback(len(warmup_flows), len(warmup_flows))

        logger.info(
            "Trained Baseline Isolation Forest on %d benign flows in %.3fs",
            len(warmup_flows),
            elapsed,
        )
        return elapsed

    def evaluate_stream(
        self,
        eval_flows: List[Dict[str, float]],
        eval_labels: List[int],
        progress_callback: Optional[Callable[[int, int, Dict[str, Any]], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """Evaluate Isolation Forest on the evaluation flows."""
        if self.model is None:
            raise RuntimeError("Isolation Forest baseline has not been trained yet.")

        total = len(eval_flows)
        tp = 0
        tn = 0
        fp = 0
        fn = 0

        predictions: List[int] = []
        latencies: List[float] = []

        X = self.flows_to_array(eval_flows)

        # Measure native batch matrix evaluation latency across the test matrix
        t_batch_start = time.perf_counter()
        _ = self.model.decision_function(X)
        batch_eval_duration = time.perf_counter() - t_batch_start
        batch_latency_per_flow_ms = (batch_eval_duration * 1000.0) / max(1, total)
        batch_throughput_fps = total / max(1e-6, batch_eval_duration)

        t_start = time.perf_counter()

        for i in range(total):
            if cancel_check and cancel_check():
                logger.warning("Isolation Forest evaluation cancelled at flow %d", i)
                break

            t0 = time.perf_counter()
            row = X[i: i + 1]
            # decision_function: positive = inlier (normal), negative = outlier (anomaly)
            decision = float(self.model.decision_function(row)[0])
            # predict returns 1 for inlier, -1 for outlier
            is_anomaly = decision < 0.0
            y_pred = 1 if is_anomaly else 0
            t1 = time.perf_counter()

            latencies.append((t1 - t0) * 1000.0)
            predictions.append(y_pred)
            y_true = eval_labels[i]

            if y_true == 1 and y_pred == 1:
                tp += 1
            elif y_true == 0 and y_pred == 0:
                tn += 1
            elif y_true == 0 and y_pred == 1:
                fp += 1
            elif y_true == 1 and y_pred == 0:
                fn += 1

            if progress_callback and (i % 250 == 0 or i == total - 1):
                interim_acc = (tp + tn) / max(1, i + 1)
                progress_callback(
                    i + 1,
                    total,
                    {
                        "accuracy": interim_acc,
                        "tp": tp,
                        "tn": tn,
                        "fp": fp,
                        "fn": fn,
                        "avg_latency_ms": sum(latencies[-100:]) / max(1, len(latencies[-100:])),
                    },
                )

        total_eval_time = time.perf_counter() - t_start
        n_eval = len(predictions)

        accuracy = (tp + tn) / max(1, n_eval)
        precision = tp / max(1, (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = tp / max(1, (tp + fn)) if (tp + fn) > 0 else 0.0
        f1_score = 2 * precision * recall / max(1e-9, (precision + recall)) if (precision + recall) > 0 else 0.0
        fpr = fp / max(1, (fp + tn)) if (fp + tn) > 0 else 0.0
        tpr = recall
        avg_latency = sum(latencies) / max(1, len(latencies))

        logger.info(
            "Isolation Forest Baseline Evaluation complete: %d flows in %.3fs (acc=%.4f, f1=%.4f, fpr=%.4f, seq_latency=%.4f ms/flow, batch_latency=%.4f ms/flow [%.0f flows/sec])",
            n_eval,
            total_eval_time,
            accuracy,
            f1_score,
            fpr,
            avg_latency,
            batch_latency_per_flow_ms,
            batch_throughput_fps,
        )

        return {
            "total_flows": n_eval,
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1_score, 4),
            "false_positive_rate": round(fpr, 4),
            "true_positive_rate": round(tpr, 4),
            "confusion_matrix": {
                "tn": tn,
                "fp": fp,
                "fn": fn,
                "tp": tp,
            },
            "total_evaluation_time_sec": round(total_eval_time, 4),
            "warmup_time_sec": round(self.warmup_duration_sec, 4),
            "avg_latency_per_flow_ms": round(avg_latency, 4),
            "sequential_latency_per_flow_ms": round(avg_latency, 4),
            "batch_latency_per_flow_ms": round(batch_latency_per_flow_ms, 4),
            "batch_throughput_flows_sec": round(batch_throughput_fps, 1),
        }
