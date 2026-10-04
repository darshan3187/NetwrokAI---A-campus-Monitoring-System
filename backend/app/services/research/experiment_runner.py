"""Reproducible Experiment Execution Engine for Network Anomaly Detection.

Orchestrates the research evaluation workflow:
- Asynchronous non-blocking background execution (UI remains completely responsive).
- Multi-run statistical evaluation (up to 12 runs with randomized seeds as in the paper).
- Real-time progress broadcasting (warm-up progress, evaluation progress, throughput).
- Support for safe cancellation.
- Model comparisons: River Online OCSVM vs. Baseline Isolation Forest.
- SQLite persistence of all experiment runs and confusion matrices.
"""

import asyncio
import json
import logging
import math
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ResearchDatasetModel, ResearchExperimentModel
from app.services.research.baseline_iforest import BaselineIsolationForest
from app.services.research.dataset_service import dataset_service
from app.services.research.online_ocsvm import RiverOnlineOCSVM

logger = logging.getLogger("network_monitoring.research.runner")


class ExperimentRunner:
    """Manages execution, thread safety, progress tracking, and persistence of experiments."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._cancel_flag = False

        # Live runtime state
        self.active_experiment_id: Optional[str] = None
        self.status = "idle"  # idle, preparing, scaler_init, warmup, evaluating, completed, cancelled, failed
        self.phase = "Ready"
        self.current_step = "No experiment currently running."
        self.warmup_progress = 0.0
        self.eval_progress = 0.0
        self.flows_processed = 0
        self.total_flows = 0
        self.flows_per_second = 0.0
        self.avg_latency_ms = 0.0
        self.current_metrics: Optional[Dict[str, float]] = None
        self.latest_result: Optional[Dict[str, Any]] = None
        self.error_message: Optional[str] = None

    def get_progress_snapshot(self) -> Dict[str, Any]:
        """Return thread-safe snapshot of live execution progress."""
        with self._lock:
            return {
                "status": self.status,
                "phase": self.phase,
                "current_step": self.current_step,
                "warmup_progress": round(self.warmup_progress, 1),
                "eval_progress": round(self.eval_progress, 1),
                "flows_processed": self.flows_processed,
                "total_flows": self.total_flows,
                "flows_per_second": round(self.flows_per_second, 1),
                "avg_latency_ms": round(self.avg_latency_ms, 4),
                "current_metrics": self.current_metrics,
                "experiment_id": self.active_experiment_id,
            }

    def cancel_active_run(self) -> bool:
        """Request graceful cancellation of the active experiment."""
        with self._lock:
            if self.status not in ("preparing", "scaler_init", "warmup", "evaluating"):
                return False
            self._cancel_flag = True
            self.current_step = "Cancellation requested; stopping background worker..."
            logger.info("Cancellation requested for experiment %s", self.active_experiment_id)
            return True

    def start_experiment(
        self,
        dataset_id: str,
        model_type: str = "river_ocsvm",
        preset_name: str = "NF-UNSW-NB15",
        is_paper_preset: bool = True,
        parameters: Optional[Dict[str, Any]] = None,
        random_seed: int = 42,
        num_runs: int = 1,
    ) -> str:
        """Start a new experiment asynchronously in a background thread."""
        with self._lock:
            if self.status in ("preparing", "scaler_init", "warmup", "evaluating"):
                raise RuntimeError("An experiment is already in progress. Please wait or cancel it first.")

            experiment_id = str(uuid.uuid4())
            self.active_experiment_id = experiment_id
            self.status = "preparing"
            self.phase = "Initializing"
            self.current_step = "Preparing dataset and random seeds..."
            self.warmup_progress = 0.0
            self.eval_progress = 0.0
            self.flows_processed = 0
            self.total_flows = 0
            self.flows_per_second = 0.0
            self.avg_latency_ms = 0.0
            self.current_metrics = None
            self.error_message = None
            self._cancel_flag = False

            # Launch background worker
            params = parameters or {}
            self._thread = threading.Thread(
                target=self._run_worker,
                args=(
                    experiment_id,
                    dataset_id,
                    model_type,
                    preset_name,
                    is_paper_preset,
                    params,
                    random_seed,
                    num_runs,
                ),
                daemon=True,
                name=f"experiment-worker-{experiment_id[:8]}",
            )
            self._thread.start()
            logger.info("Launched experiment worker thread for run %s", experiment_id)
            return experiment_id

    def _run_worker(
        self,
        experiment_id: str,
        dataset_id: str,
        model_type: str,
        preset_name: str,
        is_paper_preset: bool,
        parameters: Dict[str, Any],
        random_seed: int,
        num_runs: int,
    ) -> None:
        """Background execution loop."""
        db: Session = SessionLocal()
        try:
            # 1. Look up dataset
            dataset = db.query(ResearchDatasetModel).filter(ResearchDatasetModel.id == dataset_id).first()
            if not dataset:
                # Check if default sample is needed
                dataset = dataset_service.ensure_default_sample_dataset(db)

            # Hyperparameter defaults based on paper
            nu = float(parameters.get("nu", 0.05 if "v2" not in preset_name.lower() else 0.10))
            q = float(parameters.get("q", 0.99 if "v2" not in preset_name.lower() else 0.95))
            eta = float(parameters.get("learning_rate", 0.1 if "v2" not in preset_name.lower() else 0.3))
            power = float(parameters.get("power", 0.5))
            scaler_init_target = int(parameters.get("scaler_init_count", 1000))
            warmup_target = int(parameters.get("warmup_count", 100000))
            eval_target = parameters.get("eval_count")
            if eval_target is not None:
                eval_target = int(eval_target)

            effective_runs = max(1, min(num_runs, 12))
            run_records: List[Dict[str, Any]] = []

            for run_idx in range(effective_runs):
                if self._cancel_flag:
                    break

                current_seed = random_seed + run_idx
                with self._lock:
                    self.phase = f"Run {run_idx + 1}/{effective_runs}"
                    self.current_step = f"Partitioning dataset for run {run_idx + 1} (seed={current_seed})..."

                # Prepare splits with safeguards
                split_data = dataset_service.prepare_experiment_data(
                    file_path=dataset.file_path,
                    scaler_init_count=scaler_init_target,
                    warmup_count=warmup_target,
                    eval_count=eval_target,
                    random_seed=current_seed,
                )

                if split_data.get("config_adjusted"):
                    parameters["config_adjusted"] = True
                    parameters["adjustment_reason"] = split_data.get("adjustment_reason")
                    logger.info("Safeguard adjusted experiment configuration: %s", split_data.get("adjustment_reason"))
                else:
                    parameters["config_adjusted"] = False
                    parameters["adjustment_reason"] = "Requested configuration fits dataset size without reduction."

                scaler_flows = split_data["scaler_init_flows"]
                warmup_flows = split_data["warmup_flows"]
                eval_flows = split_data["eval_flows"]
                eval_labels = split_data["eval_labels"]

                total_run_flows = len(scaler_flows) + len(warmup_flows) + len(eval_flows)
                with self._lock:
                    self.total_flows = total_run_flows
                    self.flows_processed = 0

                # Execute requested model
                if model_type == "river_ocsvm":
                    run_result = self._execute_river_run(
                        scaler_flows,
                        warmup_flows,
                        eval_flows,
                        eval_labels,
                        nu,
                        q,
                        eta,
                        power,
                    )
                elif model_type == "isolation_forest":
                    run_result = self._execute_iforest_run(
                        warmup_flows,
                        eval_flows,
                        eval_labels,
                        contamination=float(parameters.get("contamination", 0.05)),
                        n_estimators=int(parameters.get("n_estimators", 100)),
                        seed=current_seed,
                    )
                else:
                    # Default fallback to river_ocsvm
                    run_result = self._execute_river_run(
                        scaler_flows,
                        warmup_flows,
                        eval_flows,
                        eval_labels,
                        nu,
                        q,
                        eta,
                        power,
                    )

                if run_result:
                    run_result["run_index"] = run_idx + 1
                    run_result["seed"] = current_seed
                    run_records.append(run_result)

            # Check if cancelled
            if self._cancel_flag:
                with self._lock:
                    self.status = "cancelled"
                    self.phase = "Cancelled"
                    self.current_step = "Experiment run was cancelled by user."
                logger.info("Experiment %s marked as cancelled", experiment_id)
                return

            if not run_records:
                raise RuntimeError("No completed run records produced.")

            # Compute aggregated metrics across runs
            agg = self._aggregate_runs(run_records)

            # Store in SQLite
            primary_cm = run_records[0]["confusion_matrix"]
            exp_model = ResearchExperimentModel(
                id=experiment_id,
                dataset_id=dataset.id,
                dataset_name=dataset.name,
                model_type=model_type,
                is_paper_preset=is_paper_preset,
                preset_name=preset_name,
                parameters_json=json.dumps(parameters),
                random_seed=random_seed,
                num_runs=effective_runs,
                status="completed",
                scaler_init_count=len(scaler_flows) if model_type == "river_ocsvm" else 0,
                warmup_count=len(warmup_flows),
                eval_count=len(eval_flows),
                total_evaluation_time_sec=agg["total_eval_time_sec"],
                warmup_time_sec=agg["warmup_time_sec"],
                avg_latency_per_flow_ms=agg["avg_latency_per_flow_ms"],
                accuracy=agg["accuracy"],
                precision=agg["precision"],
                recall=agg["recall"],
                f1_score=agg["f1_score"],
                false_positive_rate=agg["false_positive_rate"],
                true_positive_rate=agg["true_positive_rate"],
                confusion_matrix_json=json.dumps(primary_cm),
                runs_summary_json=(
                    json.dumps({"stats": agg.get("multi_run_stats"), "runs": run_records})
                    if effective_runs > 1
                    else None
                ),
                error_message=None,
                created_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db.add(exp_model)
            db.commit()

            with self._lock:
                self.status = "completed"
                self.phase = "Completed"
                self.current_step = (
                    f"Successfully evaluated {len(eval_flows)} flows "
                    f"(Accuracy={agg['accuracy']*100:.2f}%, F1={agg['f1_score']*100:.2f}%, "
                    f"FPR={agg['false_positive_rate']*100:.2f}%)."
                )
                self.latest_result = agg
                self.current_metrics = {
                    "accuracy": agg["accuracy"],
                    "f1_score": agg["f1_score"],
                    "recall": agg["recall"],
                    "precision": agg["precision"],
                    "fpr": agg["false_positive_rate"],
                }

            logger.info("Experiment %s successfully completed and persisted", experiment_id)

        except Exception as exc:
            logger.exception("Experiment execution failed: %s", exc)
            with self._lock:
                self.status = "failed"
                self.phase = "Error"
                self.current_step = f"Execution failed: {exc}"
                self.error_message = str(exc)

            # Persist failure record if possible
            try:
                fail_model = ResearchExperimentModel(
                    id=experiment_id,
                    dataset_id=dataset_id,
                    dataset_name=preset_name,
                    model_type=model_type,
                    is_paper_preset=is_paper_preset,
                    preset_name=preset_name,
                    parameters_json=json.dumps(parameters),
                    random_seed=random_seed,
                    num_runs=num_runs,
                    status="failed",
                    error_message=str(exc),
                    created_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                )
                db.add(fail_model)
                db.commit()
            except Exception:
                pass
        finally:
            db.close()

    def _execute_river_run(
        self,
        scaler_flows: List[Dict[str, float]],
        warmup_flows: List[Dict[str, float]],
        eval_flows: List[Dict[str, float]],
        eval_labels: List[int],
        nu: float,
        q: float,
        eta: float,
        power: float,
    ) -> Optional[Dict[str, Any]]:
        """Execute a single run of the River Online One-Class SVM."""
        model = RiverOnlineOCSVM(nu=nu, q=q, learning_rate=eta, power=power)

        # Step 1: Scaler Init
        with self._lock:
            self.current_step = f"Initializing incremental MaxAbsScaler ({len(scaler_flows)} flows)..."
        model.initialize_scaler(scaler_flows)
        if self._cancel_flag:
            return None

        # Step 2: Warm-up
        with self._lock:
            self.current_step = f"Warming up River One-Class SVM on {len(warmup_flows)} benign flows..."

        def warmup_prog(current: int, total: int):
            with self._lock:
                self.warmup_progress = (current / max(1, total)) * 100.0
                self.flows_processed = len(scaler_flows) + current

        model.warm_up(warmup_flows, progress_callback=warmup_prog)
        if self._cancel_flag:
            return None

        # Step 3: Online Streaming Evaluation
        with self._lock:
            self.current_step = f"Evaluating stream of {len(eval_flows)} flows with online conditional update..."

        t_eval_start = time.perf_counter()

        def eval_prog(current: int, total: int, metrics: Dict[str, Any]):
            with self._lock:
                self.eval_progress = (current / max(1, total)) * 100.0
                self.flows_processed = len(scaler_flows) + len(warmup_flows) + current
                elapsed = max(0.001, time.perf_counter() - t_eval_start)
                self.flows_per_second = current / elapsed
                self.avg_latency_ms = metrics.get("avg_latency_ms", 0.0)
                self.current_metrics = metrics

        results = model.evaluate_stream(
            eval_flows,
            eval_labels,
            progress_callback=eval_prog,
            cancel_check=lambda: self._cancel_flag,
        )

        return results

    def _execute_iforest_run(
        self,
        warmup_flows: List[Dict[str, float]],
        eval_flows: List[Dict[str, float]],
        eval_labels: List[int],
        contamination: float,
        n_estimators: int,
        seed: int,
    ) -> Optional[Dict[str, Any]]:
        """Execute a single run of the Baseline Isolation Forest."""
        iforest = BaselineIsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=seed,
        )

        with self._lock:
            self.current_step = f"Fitting Baseline Isolation Forest on {len(warmup_flows)} benign flows..."

        def warmup_prog(current: int, total: int):
            with self._lock:
                self.warmup_progress = (current / max(1, total)) * 100.0
                self.flows_processed = current

        iforest.train_baseline(warmup_flows, progress_callback=warmup_prog)
        if self._cancel_flag:
            return None

        with self._lock:
            self.current_step = f"Evaluating Baseline Isolation Forest on {len(eval_flows)} flows..."

        t_eval_start = time.perf_counter()

        def eval_prog(current: int, total: int, metrics: Dict[str, Any]):
            with self._lock:
                self.eval_progress = (current / max(1, total)) * 100.0
                self.flows_processed = len(warmup_flows) + current
                elapsed = max(0.001, time.perf_counter() - t_eval_start)
                self.flows_per_second = current / elapsed
                self.avg_latency_ms = metrics.get("avg_latency_ms", 0.0)
                self.current_metrics = metrics

        results = iforest.evaluate_stream(
            eval_flows,
            eval_labels,
            progress_callback=eval_prog,
            cancel_check=lambda: self._cancel_flag,
        )

        return results

    def _aggregate_runs(self, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute mean and std across multiple experimental runs."""
        n = len(runs)
        if n == 1:
            r = runs[0]
            return {
                "accuracy": r["accuracy"],
                "precision": r["precision"],
                "recall": r["recall"],
                "f1_score": r["f1_score"],
                "false_positive_rate": r["false_positive_rate"],
                "true_positive_rate": r["true_positive_rate"],
                "avg_latency_per_flow_ms": r["avg_latency_per_flow_ms"],
                "warmup_time_sec": r["warmup_time_sec"],
                "total_eval_time_sec": r["total_evaluation_time_sec"],
                "confusion_matrix": r["confusion_matrix"],
                "multi_run_stats": None,
            }

        # Multi-run aggregation
        keys = ["accuracy", "precision", "recall", "f1_score", "false_positive_rate", "true_positive_rate", "avg_latency_per_flow_ms"]
        stats = {}

        for k in keys:
            vals = [r[k] for r in runs]
            mean_val = sum(vals) / n
            var_val = sum((x - mean_val) ** 2 for x in vals) / max(1, n - 1)
            std_val = math.sqrt(var_val)
            stats[k] = {
                "mean": round(mean_val, 4),
                "std": round(std_val, 4),
            }

        primary_r = runs[0]
        return {
            "accuracy": stats["accuracy"]["mean"],
            "precision": stats["precision"]["mean"],
            "recall": stats["recall"]["mean"],
            "f1_score": stats["f1_score"]["mean"],
            "false_positive_rate": stats["false_positive_rate"]["mean"],
            "true_positive_rate": stats["true_positive_rate"]["mean"],
            "avg_latency_per_flow_ms": stats["avg_latency_per_flow_ms"]["mean"],
            "warmup_time_sec": primary_r["warmup_time_sec"],
            "total_eval_time_sec": primary_r["total_evaluation_time_sec"],
            "confusion_matrix": primary_r["confusion_matrix"],
            "multi_run_stats": stats,
        }


experiment_runner = ExperimentRunner()
