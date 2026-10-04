"""River-based Unsupervised Online One-Class SVM anomaly detection pipeline.

Paper-inspired implementation with documented adaptations based on Alberto Miguel-Diez et al. (arXiv:2509.01375):
1. Incremental MaxAbsScaler (`river.preprocessing.MaxAbsScaler`).
2. One-Class SVM with SGD and InverseScaling scheduler (`river.anomaly.OneClassSVM`).
3. QuantileFilter (`river.anomaly.QuantileFilter`) for dynamic anomaly score thresholding.
4. Conditional online model updates: only benign-classified flows update the model.
5. Strict isolation of ground-truth evaluation labels from model learning.
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from river import anomaly, optim, preprocessing

logger = logging.getLogger("network_monitoring.research.ocsvm")


class RiverOnlineOCSVM:
    """Manages the full lifecycle of the streaming One-Class SVM pipeline."""

    def __init__(
        self,
        nu: float = 0.05,
        q: float = 0.99,
        learning_rate: float = 0.1,
        power: float = 0.5,
    ) -> None:
        self.nu = nu
        self.q = q
        self.learning_rate = learning_rate
        self.power = power

        # Initialize the incremental scaler
        self.scaler = preprocessing.MaxAbsScaler()

        # Initialize the learning rate scheduler and SGD optimizer
        # eta_t = learning_rate / (1 + t)^power
        self.scheduler = optim.schedulers.InverseScaling(
            learning_rate=self.learning_rate,
            power=self.power,
        )
        self.optimizer = optim.SGD(lr=self.scheduler)

        # Initialize the online One-Class SVM
        self.ocsvm = anomaly.OneClassSVM(
            nu=self.nu,
            optimizer=self.optimizer,
        )

        # Initialize the QuantileFilter with protection enabled
        self.filter = anomaly.QuantileFilter(
            anomaly_detector=self.ocsvm,
            q=self.q,
            protect_anomaly_detector=True,
        )

        # Combine into pipeline: MaxAbsScaler | QuantileFilter(OneClassSVM)
        self.pipeline = self.scaler | self.filter

        # Lifecycle telemetry
        self.is_scaler_initialized = False
        self.is_warmed_up = False
        self.scaler_init_count = 0
        self.warmup_count = 0
        self.evaluation_count = 0
        self.benign_updates_count = 0
        self.anomalies_detected_count = 0
        self.warmup_duration_sec = 0.0

    @property
    def current_threshold(self) -> Optional[float]:
        """Current score decision threshold from Quantile tracker."""
        return self.pipeline["QuantileFilter"].quantile.get()

    def initialize_scaler(self, flows: List[Dict[str, float]]) -> None:
        """Step 1: Fit incremental MaxAbsScaler using designated benign scaler initialization flows."""
        for flow in flows:
            self.pipeline["MaxAbsScaler"].learn_one(flow)
            self.scaler_init_count += 1
        self.is_scaler_initialized = True
        logger.info("Initialized River MaxAbsScaler with %d benign flows", len(flows))

    def warm_up(
        self,
        flows: List[Dict[str, float]],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> float:
        """Step 2: Train the One-Class SVM on known benign baseline flows.

        During warm-up, the model learns typical network behavior and establishes
        the baseline distribution for quantile thresholding.
        """
        t0 = time.perf_counter()
        total = len(flows)

        for i, flow in enumerate(flows):
            self.pipeline.learn_one(flow)
            self.warmup_count += 1
            if progress_callback and (i % 500 == 0 or i == total - 1):
                progress_callback(i + 1, total)

        elapsed = time.perf_counter() - t0
        self.warmup_duration_sec = elapsed
        self.is_warmed_up = True
        logger.info(
            "Warmed up River One-Class SVM with %d benign flows in %.3fs (threshold=%.4f)",
            total,
            elapsed,
            self.current_threshold or 0.0,
        )
        return elapsed

    def predict_one(self, flow: Dict[str, float]) -> Tuple[float, bool]:
        """Step 3: Generate anomaly score and quantile-based decision.

        Returns:
            Tuple of (raw_anomaly_score, is_anomaly_boolean)
        """
        score = float(self.pipeline.score_one(flow))
        # QuantileFilter.classify returns True if score >= quantile.get() (Anomaly)
        is_anomaly = bool(self.pipeline["QuantileFilter"].classify(score))
        return score, is_anomaly

    def update_conditional(self, flow: Dict[str, float], is_anomaly: bool) -> bool:
        """Step 4: Conditional online update.

        Per Section 2.5 of the paper:
        The model is updated ONLY when the flow is classified as benign (inlier).
        If classified as an anomaly, the model weights and scaler are NOT updated.
        """
        if not is_anomaly:
            self.pipeline.learn_one(flow)
            self.benign_updates_count += 1
            return True
        else:
            self.anomalies_detected_count += 1
            return False

    def evaluate_stream(
        self,
        eval_flows: List[Dict[str, float]],
        eval_labels: List[int],
        progress_callback: Optional[Callable[[int, int, Dict[str, Any]], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """Step 5: Run full online streaming evaluation.

        Iterates flow-by-flow:
        - Calculates score
        - Classifies anomaly
        - Conditionally updates model on benign flows
        - Records evaluation metrics against isolated ground-truth labels
        """
        total = len(eval_flows)
        predictions: List[int] = []
        scores: List[float] = []
        latencies: List[float] = []
        inference_latencies: List[float] = []
        update_latencies: List[float] = []

        tp = 0
        tn = 0
        fp = 0
        fn = 0

        t_start = time.perf_counter()

        for i in range(total):
            if cancel_check and cancel_check():
                logger.warning("Online evaluation cancelled at flow %d / %d", i, total)
                break

            flow = eval_flows[i]
            y_true = eval_labels[i]

            t_flow0 = time.perf_counter()
            score, is_anomaly = self.predict_one(flow)
            t_flow_infer = time.perf_counter()
            y_pred = 1 if is_anomaly else 0

            # Conditional online model update (benign flows only)
            self.update_conditional(flow, is_anomaly)
            t_flow1 = time.perf_counter()

            infer_ms = (t_flow_infer - t_flow0) * 1000.0
            update_ms = (t_flow1 - t_flow_infer) * 1000.0
            total_flow_ms = (t_flow1 - t_flow0) * 1000.0

            inference_latencies.append(infer_ms)
            update_latencies.append(update_ms)
            latencies.append(total_flow_ms)
            predictions.append(y_pred)
            scores.append(score)

            # Update confusion matrix tallies
            if y_true == 1 and y_pred == 1:
                tp += 1
            elif y_true == 0 and y_pred == 0:
                tn += 1
            elif y_true == 0 and y_pred == 1:
                fp += 1
            elif y_true == 1 and y_pred == 0:
                fn += 1

            self.evaluation_count += 1

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

        avg_infer_latency = sum(inference_latencies) / max(1, len(inference_latencies))
        avg_update_latency = sum(update_latencies) / max(1, len(update_latencies))
        avg_latency = sum(latencies) / max(1, len(latencies))

        logger.info(
            "Online OCSVM Evaluation complete: %d flows in %.3fs (acc=%.4f, f1=%.4f, fpr=%.4f, latency=%.4f ms/flow [infer=%.4f ms, update=%.4f ms])",
            n_eval,
            total_eval_time,
            accuracy,
            f1_score,
            fpr,
            avg_latency,
            avg_infer_latency,
            avg_update_latency,
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
            "avg_inference_latency_ms": round(avg_infer_latency, 4),
            "avg_update_latency_ms": round(avg_update_latency, 4),
            "scores_summary": {
                "min": round(min(scores) if scores else 0.0, 4),
                "max": round(max(scores) if scores else 0.0, 4),
                "mean": round(sum(scores) / max(1, len(scores)), 4),
                "threshold": round(self.current_threshold or 0.0, 4),
            },
            "benign_updates_count": self.benign_updates_count,
            "anomalies_detected_count": self.anomalies_detected_count,
        }
