"""Unit and integration test suite for the Network Anomaly Simulation and Validation Lab."""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.database import Base, engine, get_db
from app.main import app
from app.models import AnomalyEventModel, NetworkMetricModel
from app.services.monitoring import monitoring_service
from app.services.simulation import (
    ConfusionMatrix,
    SimulationService,
    SimulationTimelinePoint,
    ValidationMetrics,
    simulation_service,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Ensure clean test database table isolation for each test execution."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """Test client for FastAPI REST endpoints."""
    return TestClient(app)


# ============================================================================
# 1. Scenario Generator Tests
# ============================================================================


class TestScenarioGenerators:
    """Verifies synthetic sample sequences, determinism, and ground-truth labeling."""

    @pytest.mark.parametrize(
        "scenario_id",
        [
            "normal_stable",
            "gradual_increase",
            "sudden_download_spike",
            "sudden_upload_spike",
            "unusual_packet_rate",
            "bidirectional_burst",
            "return_to_baseline",
        ],
    )
    def test_every_scenario_generator_produces_valid_samples(self, scenario_id: str):
        """Every registered scenario generates expected length, valid metrics, and non-negative values."""
        sim = SimulationService()
        definition = sim.get_scenario(scenario_id)
        assert definition is not None

        samples = sim.generate_scenario_samples(scenario_id, seed=42)
        assert len(samples) == definition.duration_seconds

        for idx, sample in enumerate(samples):
            assert sample.step == idx + 1
            assert sample.download_mbps >= 0.0
            assert sample.upload_mbps >= 0.0
            assert sample.packets_received_per_sec >= 0.0
            assert sample.packets_sent_per_sec >= 0.0
            assert sample.cumulative_bytes_sent > 0
            assert sample.cumulative_bytes_recv > 0
            assert sample.interface == "sim0"
            assert isinstance(sample.timestamp, datetime)

            # First sample must be marked as initial calibration tick
            if idx == 0:
                assert sample.is_initial_sample is True
            else:
                assert sample.is_initial_sample is False

    def test_deterministic_output_with_fixed_seed(self):
        """Identical random seeds produce exact, bit-for-bit identical metric sequences."""
        sim = SimulationService()
        samples_a = sim.generate_scenario_samples("sudden_download_spike", seed=123)
        samples_b = sim.generate_scenario_samples("sudden_download_spike", seed=123)

        assert len(samples_a) == len(samples_b)
        for sa, sb in zip(samples_a, samples_b):
            assert sa.download_mbps == sb.download_mbps
            assert sa.upload_mbps == sb.upload_mbps
            assert sa.packets_received_per_sec == sb.packets_received_per_sec
            assert sa.ground_truth_anomaly == sb.ground_truth_anomaly

    def test_different_seeds_produce_varied_noise(self):
        """Different seeds introduce unique stochastic variation while maintaining scenario profile."""
        sim = SimulationService()
        samples_1 = sim.generate_scenario_samples("normal_stable", seed=1)
        samples_2 = sim.generate_scenario_samples("normal_stable", seed=2)

        # Baseline average throughput is similar but not identical float values
        diffs = [s1.download_mbps != s2.download_mbps for s1, s2 in zip(samples_1, samples_2)]
        assert any(diffs)

    def test_ground_truth_labels_structure(self):
        """Ground truth anomaly flags conform to expected scenario event intervals."""
        sim = SimulationService()

        # normal_stable has 0 ground truth anomalies
        normal_samples = sim.generate_scenario_samples("normal_stable")
        assert all(s.ground_truth_anomaly is False for s in normal_samples)
        assert all(s.expected_severity == "Normal" for s in normal_samples)

        # sudden_download_spike has anomalies between steps 32 and 42
        spike_samples = sim.generate_scenario_samples("sudden_download_spike")
        anomalies = [s for s in spike_samples if s.ground_truth_anomaly]
        assert len(anomalies) == 11
        for a in anomalies:
            assert 32 <= a.step <= 42
            assert a.expected_severity == "High Anomaly"

        # Baseline warmup steps (1..31) are never labeled as anomalous
        for s in spike_samples[:31]:
            assert s.ground_truth_anomaly is False


# ============================================================================
# 2. Validation Pipeline and Metric Calculation Tests
# ============================================================================


class TestValidationMetricsCalculation:
    """Verifies precision, recall, F1, accuracy, latency, and division-by-zero handling."""

    def test_confusion_matrix_and_metrics_with_known_vectors(self):
        """Calculates exact statistical measures against a known synthetic timeline."""
        sim = SimulationService()
        now = datetime.now()

        # 10 samples: 3 TP, 4 TN, 2 FP, 1 FN
        test_points = [
            # 3 TP (detected & true anomaly)
            SimulationTimelinePoint(1, now, 10, 2, 800, True, "High", 0.85, "High", True, "if", ""),
            SimulationTimelinePoint(2, now, 10, 2, 800, True, "High", 0.82, "High", True, "if", ""),
            SimulationTimelinePoint(3, now, 10, 2, 800, True, "High", 0.78, "Unusual", True, "if", ""),
            # 4 TN (not detected & not anomaly)
            SimulationTimelinePoint(4, now, 10, 2, 800, False, "Normal", 0.1, "Normal", False, "if", ""),
            SimulationTimelinePoint(5, now, 10, 2, 800, False, "Normal", 0.2, "Normal", False, "if", ""),
            SimulationTimelinePoint(6, now, 10, 2, 800, False, "Normal", 0.15, "Normal", False, "if", ""),
            SimulationTimelinePoint(7, now, 10, 2, 800, False, "Normal", 0.05, "Normal", False, "if", ""),
            # 2 FP (detected & not anomaly)
            SimulationTimelinePoint(8, now, 10, 2, 800, False, "Normal", 0.65, "Unusual", True, "if", ""),
            SimulationTimelinePoint(9, now, 10, 2, 800, False, "Normal", 0.70, "Unusual", True, "if", ""),
            # 1 FN (not detected & true anomaly)
            SimulationTimelinePoint(10, now, 10, 2, 800, True, "High", 0.40, "Normal", False, "if", ""),
        ]

        cm, metrics = sim._calculate_validation_metrics(test_points)

        assert cm.true_positives == 3
        assert cm.true_negatives == 4
        assert cm.false_positives == 2
        assert cm.false_negatives == 1
        assert cm.total_samples == 10

        # Accuracy: (3 + 4) / 10 = 0.70
        assert metrics.accuracy == pytest.approx(0.70)
        # Precision: 3 / (3 + 2) = 0.60
        assert metrics.precision == pytest.approx(0.60)
        # Recall: 3 / (3 + 1) = 0.75
        assert metrics.recall == pytest.approx(0.75)
        # F1: 2 * (0.6 * 0.75) / (0.6 + 0.75) = 0.9 / 1.35 = 0.6667
        assert metrics.f1_score == pytest.approx(0.6667, rel=1e-3)
        # Latency: first anomaly at step 1, first detection at step 1 -> latency = 0.0s
        assert metrics.detection_latency_seconds == 0.0

    def test_zero_division_behavior_with_all_normal_scenario(self):
        """When scenario has 0 positive labels and model has 0 false positives, metrics represent undefined precision/recall as None."""
        sim = SimulationService()
        now = datetime.now()

        # All 5 samples are normal and correctly predicted normal (TP=0, FP=0, FN=0, TN=5)
        all_normal = [
            SimulationTimelinePoint(i, now, 8, 2, 500, False, "Normal", 0.1, "Normal", False, "if", "")
            for i in range(1, 6)
        ]

        cm, metrics = sim._calculate_validation_metrics(all_normal)
        assert cm.true_positives == 0
        assert cm.true_negatives == 5
        assert cm.false_positives == 0
        assert cm.false_negatives == 0

        # Accuracy is mathematically well-defined: (0 + 5) / 5 = 1.0 (100%)
        assert metrics.accuracy == 1.0
        # Precision (0/0), Recall (0/0), F1 are mathematically undefined and returned as None
        assert metrics.precision is None
        assert metrics.recall is None
        assert metrics.f1_score is None
        # Latency is None because no anomaly occurred
        assert metrics.detection_latency_seconds is None

    def test_metrics_with_all_anomaly_scenario(self):
        """When all samples are anomalous and all are detected, metrics reach 1.0."""
        sim = SimulationService()
        now = datetime.now()

        # 5 samples, all ground-truth anomalies, all correctly detected
        all_anomalous = [
            SimulationTimelinePoint(i, now, 100, 50, 5000, True, "High", 0.85, "High Anomaly", True, "if", "")
            for i in range(1, 6)
        ]

        cm, metrics = sim._calculate_validation_metrics(all_anomalous)
        assert cm.true_positives == 5
        assert cm.true_negatives == 0
        assert cm.false_positives == 0
        assert cm.false_negatives == 0

        assert metrics.accuracy == 1.0
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1_score == 1.0
        # First anomaly at step 1, first detection at step 1 -> 0.0s
        assert metrics.detection_latency_seconds == 0.0

    def test_undefined_precision_when_zero_alarms_and_false_negatives(self):
        """When detector makes zero alarms (TP=0, FP=0) but actual anomalies exist (FN>0), precision is None, recall is 0.0."""
        sim = SimulationService()
        now = datetime.now()

        # 4 samples: 2 normal correctly classified, 2 anomalies missed
        points = [
            SimulationTimelinePoint(1, now, 8, 2, 500, False, "Normal", 0.1, "Normal", False, "if", ""),
            SimulationTimelinePoint(2, now, 8, 2, 500, False, "Normal", 0.1, "Normal", False, "if", ""),
            SimulationTimelinePoint(3, now, 100, 2, 5000, True, "High", 0.3, "Normal", False, "if", ""),  # Missed
            SimulationTimelinePoint(4, now, 100, 2, 5000, True, "High", 0.3, "Normal", False, "if", ""),  # Missed
        ]

        cm, metrics = sim._calculate_validation_metrics(points)
        assert cm.true_positives == 0
        assert cm.false_positives == 0
        assert cm.false_negatives == 2
        assert cm.true_negatives == 2

        assert metrics.accuracy == 0.50
        assert metrics.precision is None  # TP / (TP + FP) = 0/0 -> None
        assert metrics.recall == 0.0     # TP / (TP + FN) = 0/2 -> 0.0
        assert metrics.f1_score is None   # Undefined because precision is None
        # Anomaly occurred at step 3, but was never detected -> latency must be None (unreached)
        assert metrics.detection_latency_seconds is None

    def test_zero_precision_when_false_positives_and_no_true_positives(self):
        """When detector raises false alarms (FP>0) but achieves zero true positives (TP=0), precision is 0.0."""
        sim = SimulationService()
        now = datetime.now()

        # 3 samples: 1 normal classified as normal, 2 normal classified as anomaly (FP=2)
        points = [
            SimulationTimelinePoint(1, now, 8, 2, 500, False, "Normal", 0.1, "Normal", False, "if", ""),
            SimulationTimelinePoint(2, now, 8, 2, 500, False, "Normal", 0.65, "High", True, "if", ""),   # FP
            SimulationTimelinePoint(3, now, 8, 2, 500, False, "Normal", 0.70, "High", True, "if", ""),   # FP
        ]

        cm, metrics = sim._calculate_validation_metrics(points)
        assert cm.true_positives == 0
        assert cm.false_positives == 2
        assert cm.true_negatives == 1
        assert cm.false_negatives == 0

        assert metrics.accuracy == pytest.approx(1 / 3)
        assert metrics.precision == 0.0  # 0 / (0 + 2) = 0.0
        assert metrics.recall is None    # 0 / (0 + 0) = Undefined (no actual anomalies)
        assert metrics.f1_score is None  # Undefined
        assert metrics.detection_latency_seconds is None

    def test_unreached_detection_latency_distinguished_from_zero(self):
        """Clearly distinguishes a missing detection (None) from an instantaneous 0.0s detection."""
        sim = SimulationService()
        now = datetime.now()

        # Scenario A: Anomaly at step 10, detected at step 10 -> latency = 0.0s
        detected_points = [
            SimulationTimelinePoint(i, now, 8, 2, 500, False, "Normal", 0.1, "Normal", False, "if", "")
            for i in range(1, 10)
        ] + [
            SimulationTimelinePoint(10, now, 100, 2, 5000, True, "High", 0.85, "High", True, "if", "")
        ]
        _, metrics_a = sim._calculate_validation_metrics(detected_points)
        assert metrics_a.detection_latency_seconds == 0.0

        # Scenario B: Anomaly at step 10, NEVER detected -> latency = None (unreached)
        missed_points = [
            SimulationTimelinePoint(i, now, 8, 2, 500, False, "Normal", 0.1, "Normal", False, "if", "")
            for i in range(1, 10)
        ] + [
            SimulationTimelinePoint(10, now, 100, 2, 5000, True, "High", 0.40, "Normal", False, "if", "")
        ]
        _, metrics_b = sim._calculate_validation_metrics(missed_points)
        assert metrics_b.detection_latency_seconds is None

    def test_detection_latency_calculation_with_delay(self):
        """Calculates correct latency when detector lags behind anomaly onset."""
        sim = SimulationService()
        now = datetime.now()

        # Anomaly onset at step 5, but model first flags it at step 8 -> latency = 3.0 seconds
        delayed_points = [
            SimulationTimelinePoint(1, now, 8, 2, 500, False, "Normal", 0.1, "Normal", False, "if", ""),
            SimulationTimelinePoint(2, now, 8, 2, 500, False, "Normal", 0.1, "Normal", False, "if", ""),
            SimulationTimelinePoint(3, now, 8, 2, 500, False, "Normal", 0.1, "Normal", False, "if", ""),
            SimulationTimelinePoint(4, now, 8, 2, 500, False, "Normal", 0.1, "Normal", False, "if", ""),
            SimulationTimelinePoint(5, now, 100, 2, 5000, True, "High", 0.45, "Normal", False, "if", ""),  # Onset
            SimulationTimelinePoint(6, now, 100, 2, 5000, True, "High", 0.50, "Normal", False, "if", ""),
            SimulationTimelinePoint(7, now, 100, 2, 5000, True, "High", 0.55, "Normal", False, "if", ""),
            SimulationTimelinePoint(8, now, 100, 2, 5000, True, "High", 0.75, "High", True, "if", ""),    # First detect
        ]

        _, metrics = sim._calculate_validation_metrics(delayed_points)
        assert metrics.detection_latency_seconds == 3.0


# ============================================================================
# 3. Simulation REST API Tests
# ============================================================================


class TestSimulationApiEndpoints:
    """Tests for /api/v1/simulation REST endpoints."""

    def test_get_scenarios_list(self, client: TestClient):
        """GET /api/v1/simulation/scenarios returns all registered scenarios and metadata."""
        resp = client.get("/api/v1/simulation/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert "scenarios" in data
        assert data["count"] == 7

        scenario_ids = [s["scenario_id"] for s in data["scenarios"]]
        assert "normal_stable" in scenario_ids
        assert "sudden_download_spike" in scenario_ids
        assert "sudden_upload_spike" in scenario_ids
        assert "unusual_packet_rate" in scenario_ids
        assert "bidirectional_burst" in scenario_ids
        assert "return_to_baseline" in scenario_ids
        assert "gradual_increase" in scenario_ids

    def test_run_simulation_valid_scenario(self, client: TestClient):
        """POST /api/v1/simulation/run executes successfully and returns full validation outcome."""
        payload = {"scenario_id": "sudden_download_spike", "seed": 42}
        resp = client.post("/api/v1/simulation/run", json=payload)
        assert resp.status_code == 200

        data = resp.json()
        assert data["scenario_id"] == "sudden_download_spike"
        assert data["duration_seconds"] == 60
        assert "confusion_matrix" in data
        assert "metrics" in data
        assert "timeline" in data
        assert len(data["timeline"]) == 60
        assert "disclaimer" in data

        # Confusion matrix checks
        cm = data["confusion_matrix"]
        assert cm["total_samples"] == 60
        assert cm["true_positives"] >= 10

        # Metrics checks
        m = data["metrics"]
        assert m["accuracy"] >= 0.90
        assert m["recall"] >= 0.90
        assert m["detection_latency_seconds"] == 0.0

    def test_run_simulation_invalid_scenario_id(self, client: TestClient):
        """POST /api/v1/simulation/run with unknown scenario ID returns HTTP 400."""
        payload = {"scenario_id": "non_existent_exploit", "seed": 42}
        resp = client.post("/api/v1/simulation/run", json=payload)
        assert resp.status_code == 400
        assert "Unknown scenario ID" in resp.json()["detail"]

    def test_get_simulation_results_after_run(self, client: TestClient):
        """GET /api/v1/simulation/results retrieves latest executed run."""
        # 1. Run simulation
        client.post("/api/v1/simulation/run", json={"scenario_id": "normal_stable", "seed": 42})

        # 2. Query results
        resp = client.get("/api/v1/simulation/results")
        assert resp.status_code == 200
        assert resp.json()["scenario_id"] == "normal_stable"
        assert resp.json()["metrics"]["accuracy"] == 1.0

    def test_reset_simulation_clears_results(self, client: TestClient):
        """POST /api/v1/simulation/reset clears cached results and causes GET to return 404."""
        # 1. Run simulation
        client.post("/api/v1/simulation/run", json={"scenario_id": "normal_stable", "seed": 42})

        # 2. Reset
        reset_resp = client.post("/api/v1/simulation/reset")
        assert reset_resp.status_code == 200
        assert reset_resp.json()["status"] == "ok"

        # 3. Query should now return 404
        get_resp = client.get("/api/v1/simulation/results")
        assert get_resp.status_code == 404


# ============================================================================
# 4. Strict Isolation Tests (Simulation vs Production Monitoring)
# ============================================================================


class TestSimulationIsolation:
    """Verifies that simulation runs cannot alter host monitoring or pollute SQLite store."""

    def test_simulation_does_not_modify_active_monitoring_interface(self, client: TestClient):
        """Simulation execution leaves production monitoring service interface untouched."""
        initial_interface = monitoring_service.active_interface

        # Run simulation with synthetic 'sim0' adapter
        client.post("/api/v1/simulation/run", json={"scenario_id": "sudden_download_spike", "seed": 42})

        # Production active interface must remain identical
        assert monitoring_service.active_interface == initial_interface

    def test_simulation_does_not_persist_events_to_database(self, client: TestClient):
        """Simulated anomaly events are never written to SQLite anomaly_events or network_metrics tables."""
        db = next(get_db())
        try:
            initial_anomaly_count = db.query(AnomalyEventModel).count()
            initial_metric_count = db.query(NetworkMetricModel).count()

            # Execute multi-burst scenario
            client.post("/api/v1/simulation/run", json={"scenario_id": "bidirectional_burst", "seed": 42})

            # Database row counts must not change by a single row
            final_anomaly_count = db.query(AnomalyEventModel).count()
            final_metric_count = db.query(NetworkMetricModel).count()

            assert final_anomaly_count == initial_anomaly_count
            assert final_metric_count == initial_metric_count
        finally:
            db.close()


# ============================================================================
# 5. Scientific Reliability and Multi-Seed Regression Tests (Phase 5.2)
# ============================================================================


class TestSimulationEvaluationReliability:
    """Verifies multi-seed determinism, drift behavior, recovery, and undefined metric API contracts."""

    def test_multiseed_reproducibility(self):
        """Identical seeds produce bit-identical results, while different seeds produce distinct noise."""
        sim = SimulationService()

        # Same seed produces bit-identical simulation results
        res_a1 = sim.run_simulation("sudden_download_spike", seed=42)
        res_a2 = sim.run_simulation("sudden_download_spike", seed=42)

        assert res_a1.confusion_matrix.true_positives == res_a2.confusion_matrix.true_positives
        assert res_a1.confusion_matrix.false_positives == res_a2.confusion_matrix.false_positives
        assert res_a1.metrics.accuracy == res_a2.metrics.accuracy
        assert res_a1.metrics.f1_score == res_a2.metrics.f1_score
        assert [p.predicted_score for p in res_a1.timeline] == [p.predicted_score for p in res_a2.timeline]

        # Different seed produces varied noise but consistent detection
        res_b = sim.run_simulation("sudden_download_spike", seed=101)
        assert res_b.metrics.recall == 1.0  # Consistently detects burst
        assert [p.download_mbps for p in res_a1.timeline] != [p.download_mbps for p in res_b.timeline]

    def test_gradual_drift_behavior_produces_documented_fp(self):
        """Verifies that static baseline Isolation Forest produces false alarms under secular drift."""
        sim = SimulationService()
        res = sim.run_simulation("gradual_increase", seed=42)

        # Scenario has 0 actual ground truth anomalies
        assert res.confusion_matrix.true_positives == 0
        assert res.confusion_matrix.false_negatives == 0
        # Secular drift outside 8.5 Mbps baseline produces documented false positives
        assert res.confusion_matrix.false_positives > 10
        # Precision is 0.0 because alarms were raised on normal drift
        assert res.metrics.precision == 0.0
        # Recall is None because denominator (actual positives) is zero
        assert res.metrics.recall is None
        assert res.metrics.f1_score is None
        assert res.metrics.detection_latency_seconds is None

    def test_sudden_spike_instant_detection_and_recovery(self):
        """Verifies immediate 0.0s detection of high-volume bursts and return to baseline."""
        sim = SimulationService()
        res = sim.run_simulation("return_to_baseline", seed=42)

        # All 11 burst steps detected
        assert res.confusion_matrix.true_positives == 11
        assert res.confusion_matrix.false_negatives == 0
        assert res.metrics.recall == 1.0
        # Immediate onset detection (step 32 detected at step 32)
        assert res.metrics.detection_latency_seconds == 0.0

        # Post-recovery telemetry (steps 43..60) return to baseline rates (< 15 Mbps)
        post_recovery = [p for p in res.timeline if p.step >= 43]
        assert len(post_recovery) == 18
        for p in post_recovery:
            assert p.download_mbps < 15.0
            assert p.ground_truth_anomaly is False

    def test_api_contract_undefined_metrics_json_serialization(self, client: TestClient):
        """REST API correctly serializes undefined precision, recall, and f1_score as null in JSON."""
        resp = client.post("/api/v1/simulation/run", json={"scenario_id": "normal_stable", "seed": 42})
        assert resp.status_code == 200
        data = resp.json()

        metrics = data["metrics"]
        assert metrics["accuracy"] == 1.0
        assert metrics["precision"] is None
        assert metrics["recall"] is None
        assert metrics["f1_score"] is None
        assert metrics["detection_latency_seconds"] is None

