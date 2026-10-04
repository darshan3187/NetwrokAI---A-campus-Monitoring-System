"""Unit and integration tests for research paper implementation.

Verifies:
- Alberto Miguel-Diez et al. (arXiv:2509.01375) methodology.
- River Online One-Class SVM with MaxAbsScaler and QuantileFilter.
- Feature preprocessing and IPv4 integer conversion via `ipaddress`.
- Label leakage prevention (target labels strictly isolated from model inputs).
- Conditional online update (only benign flows update the model).
- Baseline Isolation Forest execution and comparison.
- Metrics calculation (Accuracy, Precision, Recall, F1, FPR, TPR, Confusion Matrix).
- Multi-run randomized seeds and experiment persistence.
- REST API endpoints for research datasets and experiments.
"""

import math
import os
import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db, init_db
from app.main import app
from app.models import ResearchDatasetModel, ResearchExperimentModel
from app.services.research.baseline_iforest import BaselineIsolationForest
from app.services.research.dataset_service import (
    PRIMARY_FEATURES,
    DatasetService,
    dataset_service,
    ip_to_int,
    sanitize_float,
    sanitize_int,
)
from app.services.research.experiment_runner import ExperimentRunner
from app.services.research.online_ocsvm import RiverOnlineOCSVM
from app.services.research.reference_data import (
    PAPER_METADATA,
    PUBLISHED_PAPER_RESULTS,
    get_paper_reference_by_dataset,
)


# Test database fixture
@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    init_db(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    # Seed default sample dataset for API tests
    dataset_service.ensure_default_sample_dataset(db)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)



@pytest.fixture
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ============================================================================
# Preprocessing and IP Conversion Tests
# ============================================================================


def test_ip_to_int_standard_dotted_quad():
    """Verify standard dotted-quad IPv4 string conversion."""
    assert ip_to_int("192.168.1.1") == 3232235777
    assert ip_to_int("10.0.0.1") == 167772161
    assert ip_to_int("127.0.0.1") == 2130706433
    assert ip_to_int("0.0.0.0") == 0
    assert ip_to_int("255.255.255.255") == 4294967295


def test_ip_to_int_varied_representations():
    """Verify numeric strings, integers, floats, and edge cases."""
    assert ip_to_int(3232235777) == 3232235777
    assert ip_to_int("3232235777") == 3232235777
    assert ip_to_int(3232235777.0) == 3232235777
    assert ip_to_int("192.168.1.1/24") == 3232235777
    assert ip_to_int("192.168.1.1:8080") == 3232235777
    assert ip_to_int("invalid_ip") == 0
    assert ip_to_int(None) == 0
    assert ip_to_int(float("nan")) == 0


def test_numeric_sanitizers():
    """Verify safe float and integer bounding."""
    assert sanitize_float("123.45") == 123.45
    assert sanitize_float("nan", default=0.0) == 0.0
    assert sanitize_float(float("inf"), default=0.0) == 0.0
    assert sanitize_float("-10.0", default=0.0) == 0.0  # Clamped to positive

    assert sanitize_int("80", default=0, min_val=0, max_val=65535) == 80
    assert sanitize_int("70000", default=0, min_val=0, max_val=65535) == 65535
    assert sanitize_int("invalid", default=6) == 6


# ============================================================================
# Dataset Service Tests
# ============================================================================


def test_dataset_service_sample_generation():
    """Verify bundled benchmark sample dataset generation and column compliance."""
    temp_dir = tempfile.mkdtemp()
    try:
        svc = DatasetService(data_dir=temp_dir)
        sample_path = svc.generate_benchmark_sample_file()
        assert os.path.exists(sample_path)

        stats = svc.inspect_dataset_file(sample_path)
        assert stats["total_flows"] == 5000
        assert stats["benign_flows"] == 4000
        assert stats["attack_flows"] == 1000
        assert stats["has_label_column"] is True
        for feat in PRIMARY_FEATURES:
            assert feat in stats["detected_features"]
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dataset_label_isolation():
    """Verify that target labels are NEVER leaked into the features dictionary."""
    svc = DatasetService()
    header = PRIMARY_FEATURES + ["Label", "Attack"]
    mapping = svc.resolve_column_mapping(header)

    sample_row = {
        "IPV4_SRC_ADDR": "192.168.1.100",
        "IPV4_DST_ADDR": "10.0.0.1",
        "L4_SRC_PORT": "54321",
        "L4_DST_PORT": "443",
        "PROTOCOL": "6",
        "IN_BYTES": "2048",
        "OUT_BYTES": "4096",
        "FLOW_DURATION_MILLISECONDS": "150.5",
        "Label": "1",
        "Attack": "DDoS",
    }

    features, label = svc.parse_flow_row(sample_row, mapping)

    # Label must be correctly parsed
    assert label == 1
    # Target label or attack name must NOT exist inside features dict
    assert "Label" not in features
    assert "label" not in features
    assert "Attack" not in features
    assert "attack" not in features
    assert len(features) == len(PRIMARY_FEATURES)


def test_dataset_preparation_splits():
    """Verify scaler_init, warm-up, and balanced evaluation split partitioning."""
    temp_dir = tempfile.mkdtemp()
    try:
        svc = DatasetService(data_dir=temp_dir)
        sample_path = svc.generate_benchmark_sample_file()

        splits = svc.prepare_experiment_data(
            file_path=sample_path,
            scaler_init_count=100,
            warmup_count=500,
            eval_count=400,
            random_seed=42,
        )

        assert splits["actual_scaler_init_count"] == 100
        assert splits["actual_warmup_count"] == 500
        # Evaluation set must be balanced: 200 benign + 200 attack = 400
        assert splits["actual_eval_count"] == 400
        assert splits["eval_benign_count"] == 200
        assert splits["eval_attack_count"] == 200

        # Check that eval_labels has exactly 200 zeros and 200 ones
        labels = splits["eval_labels"]
        assert labels.count(0) == 200
        assert labels.count(1) == 200

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# River Online One-Class SVM Pipeline Tests
# ============================================================================


def test_river_pipeline_creation_and_warmup():
    """Verify River One-Class SVM initialization, scaler fitting, and warm-up."""
    model = RiverOnlineOCSVM(nu=0.05, q=0.99, learning_rate=0.1, power=0.5)
    assert model.nu == 0.05
    assert model.q == 0.99
    assert model.learning_rate == 0.1

    # Scaler init with 20 dummy benign flows
    scaler_flows = [
        {
            "IPV4_SRC_ADDR": float(ip_to_int(f"192.168.1.{i}")),
            "IPV4_DST_ADDR": float(ip_to_int("10.0.0.1")),
            "L4_SRC_PORT": float(50000 + i),
            "L4_DST_PORT": 80.0,
            "PROTOCOL": 6.0,
            "IN_BYTES": float(1000 + i * 10),
            "OUT_BYTES": 500.0,
            "FLOW_DURATION_MILLISECONDS": 50.0,
        }
        for i in range(20)
    ]
    model.initialize_scaler(scaler_flows)
    assert model.is_scaler_initialized is True
    assert model.scaler_init_count == 20

    # Warmup with 50 benign flows
    warmup_flows = [
        {
            "IPV4_SRC_ADDR": float(ip_to_int("192.168.1.50")),
            "IPV4_DST_ADDR": float(ip_to_int("10.0.0.1")),
            "L4_SRC_PORT": float(51000 + i),
            "L4_DST_PORT": 443.0,
            "PROTOCOL": 6.0,
            "IN_BYTES": float(2000 + i * 5),
            "OUT_BYTES": 1200.0,
            "FLOW_DURATION_MILLISECONDS": 80.0,
        }
        for i in range(50)
    ]
    elapsed = model.warm_up(warmup_flows)
    assert model.is_warmed_up is True
    assert model.warmup_count == 50
    assert elapsed > 0.0
    assert model.current_threshold is not None


def test_river_conditional_update_behavior():
    """Verify that only flows classified as benign update the model, protecting against anomalies."""
    model = RiverOnlineOCSVM(nu=0.05, q=0.95, learning_rate=0.1, power=0.5)

    benign_flow = {
        "IPV4_SRC_ADDR": float(ip_to_int("192.168.1.10")),
        "IPV4_DST_ADDR": float(ip_to_int("10.0.0.1")),
        "L4_SRC_PORT": 50000.0,
        "L4_DST_PORT": 80.0,
        "PROTOCOL": 6.0,
        "IN_BYTES": 1500.0,
        "OUT_BYTES": 500.0,
        "FLOW_DURATION_MILLISECONDS": 50.0,
    }

    # Warm up with identical benign patterns
    model.warm_up([benign_flow] * 30)

    # Initial benign update
    updated = model.update_conditional(benign_flow, is_anomaly=False)
    assert updated is True
    assert model.benign_updates_count == 1
    assert model.anomalies_detected_count == 0

    # Anomalous flow - must NOT update model
    updated_anom = model.update_conditional(benign_flow, is_anomaly=True)
    assert updated_anom is False
    assert model.benign_updates_count == 1
    assert model.anomalies_detected_count == 1


def test_river_evaluation_metrics_computation():
    """Verify evaluation metrics: Accuracy, Precision, Recall, F1, FPR, TPR, and Latency."""
    model = RiverOnlineOCSVM(nu=0.05, q=0.99, learning_rate=0.1)

    benign_flow = {
        "IPV4_SRC_ADDR": float(ip_to_int("192.168.1.10")),
        "IPV4_DST_ADDR": float(ip_to_int("10.0.0.1")),
        "L4_SRC_PORT": 50000.0,
        "L4_DST_PORT": 80.0,
        "PROTOCOL": 6.0,
        "IN_BYTES": 1500.0,
        "OUT_BYTES": 500.0,
        "FLOW_DURATION_MILLISECONDS": 50.0,
    }
    model.warm_up([benign_flow] * 30)

    eval_flows = [benign_flow] * 20
    eval_labels = [0] * 20  # All benign

    res = model.evaluate_stream(eval_flows, eval_labels)
    assert res["total_flows"] == 20
    assert 0.0 <= res["accuracy"] <= 1.0
    assert 0.0 <= res["false_positive_rate"] <= 1.0
    assert res["avg_latency_per_flow_ms"] >= 0.0
    assert "confusion_matrix" in res
    assert "tn" in res["confusion_matrix"]
    assert "tp" in res["confusion_matrix"]


# ============================================================================
# Baseline Isolation Forest Tests
# ============================================================================


def test_isolation_forest_baseline_execution():
    """Verify baseline Isolation Forest fits and evaluates on flow features."""
    iforest = BaselineIsolationForest(contamination=0.05, n_estimators=50, random_state=42)

    flows = [
        {
            "IPV4_SRC_ADDR": float(ip_to_int(f"192.168.1.{i}")),
            "IPV4_DST_ADDR": float(ip_to_int("10.0.0.1")),
            "L4_SRC_PORT": float(50000 + i),
            "L4_DST_PORT": 80.0,
            "PROTOCOL": 6.0,
            "IN_BYTES": float(1000 + i * 20),
            "OUT_BYTES": 500.0,
            "FLOW_DURATION_MILLISECONDS": 50.0,
        }
        for i in range(40)
    ]

    elapsed = iforest.train_baseline(flows)
    assert elapsed > 0.0
    assert iforest.model is not None

    res = iforest.evaluate_stream(flows[:20], [0] * 20)
    assert res["total_flows"] == 20
    assert 0.0 <= res["accuracy"] <= 1.0
    assert 0.0 <= res["false_positive_rate"] <= 1.0
    assert "confusion_matrix" in res


# ============================================================================
# Reference Benchmark Data Tests
# ============================================================================


def test_paper_reference_benchmarks():
    """Verify reference benchmark dataset metadata and citations."""
    assert len(PUBLISHED_PAPER_RESULTS) >= 2
    assert PAPER_METADATA["arxiv_id"] == "2509.01375"
    assert "Alberto Miguel-Diez" in PAPER_METADATA["authors"]

    ref_v1 = get_paper_reference_by_dataset("NF-UNSW-NB15")
    assert ref_v1["dataset_name"] == "NF-UNSW-NB15"
    assert ref_v1["nu"] == 0.05
    assert ref_v1["q"] == 0.99
    assert ref_v1["learning_rate"] == 0.1

    ref_v2 = get_paper_reference_by_dataset("NF-UNSW-NB15-v2")
    assert ref_v2["dataset_name"] == "NF-UNSW-NB15-v2"
    assert ref_v2["nu"] == 0.10
    assert ref_v2["q"] == 0.95
    assert ref_v2["learning_rate"] == 0.3


# ============================================================================
# REST API Integration Tests
# ============================================================================


def test_api_list_datasets(client):
    """Verify GET /api/v1/research/datasets returns sample dataset."""
    response = client.get("/api/v1/research/datasets")
    assert response.status_code == 200
    data = response.json()
    assert "datasets" in data
    assert "count" in data
    assert data["count"] >= 1
    # Check default sample presence
    sample = next((d for d in data["datasets"] if d["is_sample"] is True), None)
    assert sample is not None
    assert "NF-UNSW-NB15" in sample["name"]


def test_api_get_dataset_detail(client):
    """Verify GET /api/v1/research/datasets/{id} returns details and validation."""
    list_resp = client.get("/api/v1/research/datasets")
    datasets = list_resp.json()["datasets"]
    dataset_id = datasets[0]["id"]

    resp = client.get(f"/api/v1/research/datasets/{dataset_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dataset"]["id"] == dataset_id
    assert "validation" in data
    assert data["validation"]["is_paper_compliant"] is True
    assert len(data["sample_rows"]) > 0


def test_api_get_reference_benchmarks(client):
    """Verify GET /api/v1/research/reference returns paper published benchmarks."""
    resp = client.get("/api/v1/research/reference")
    assert resp.status_code == 200
    refs = resp.json()
    assert len(refs) >= 2
    assert any(r["dataset_name"] == "NF-UNSW-NB15" for r in refs)
    assert any(r["dataset_name"] == "NF-UNSW-NB15-v2" for r in refs)


def test_api_get_comparison_summary(client):
    """Verify GET /api/v1/research/compare returns comparison structure."""
    resp = client.get("/api/v1/research/compare")
    assert resp.status_code == 200
    data = resp.json()
    assert "paper_reference" in data
    assert len(data["paper_reference"]) >= 2
    assert "proposed_model" in data
    assert "baseline_model" in data


# ============================================================================
# Multi-Run Statistics & Fairness Tests
# ============================================================================


def test_experiment_runner_aggregate_runs_single():
    """Verify that a single run (n=1) does not fabricate a standard deviation."""
    runner = ExperimentRunner()
    single_run = [
        {
            "accuracy": 0.85,
            "precision": 0.80,
            "recall": 0.75,
            "f1_score": 0.7742,
            "false_positive_rate": 0.05,
            "true_positive_rate": 0.75,
            "avg_latency_per_flow_ms": 0.012,
            "warmup_time_sec": 0.5,
            "total_evaluation_time_sec": 1.2,
            "confusion_matrix": {"tn": 95, "fp": 5, "fn": 25, "tp": 75},
        }
    ]
    agg = runner._aggregate_runs(single_run)
    assert agg["accuracy"] == 0.85
    assert agg["f1_score"] == 0.7742
    assert agg["multi_run_stats"] is None  # Must NOT fabricate std dev for n=1


def test_experiment_runner_aggregate_runs_multi():
    """Verify that multi-run aggregation computes correct sample mean and Bessel-corrected sample std dev."""
    runner = ExperimentRunner()
    runs = [
        {
            "accuracy": 0.80,
            "precision": 0.75,
            "recall": 0.70,
            "f1_score": 0.7241,
            "false_positive_rate": 0.08,
            "true_positive_rate": 0.70,
            "avg_latency_per_flow_ms": 0.010,
            "warmup_time_sec": 0.4,
            "total_evaluation_time_sec": 1.0,
            "confusion_matrix": {"tn": 92, "fp": 8, "fn": 30, "tp": 70},
        },
        {
            "accuracy": 0.90,
            "precision": 0.85,
            "recall": 0.80,
            "f1_score": 0.8242,
            "false_positive_rate": 0.04,
            "true_positive_rate": 0.80,
            "avg_latency_per_flow_ms": 0.012,
            "warmup_time_sec": 0.5,
            "total_evaluation_time_sec": 1.1,
            "confusion_matrix": {"tn": 96, "fp": 4, "fn": 20, "tp": 80},
        },
    ]
    agg = runner._aggregate_runs(runs)
    assert agg["multi_run_stats"] is not None
    # Mean of 0.80 and 0.90 is 0.85
    assert agg["accuracy"] == 0.85
    # Sample std of [0.80, 0.90] with n=2: sqrt((0.05^2 + 0.05^2) / 1) = sqrt(0.005) = 0.0707
    acc_std = agg["multi_run_stats"]["accuracy"]["std"]
    assert math.isclose(acc_std, 0.0707, abs_tol=1e-3)
    # Check that latency is aggregated
    assert math.isclose(agg["avg_latency_per_flow_ms"], 0.011, abs_tol=1e-3)


def test_max_abs_scaler_mathematical_range():
    """Verify that MaxAbsScaler maps non-negative features into [0, 1] and signed features into [-1, 1]."""
    from river import preprocessing

    scaler = preprocessing.MaxAbsScaler()
    # Non-negative network features
    flows = [
        {"port": 80.0, "bytes": 1000.0},
        {"port": 443.0, "bytes": 5000.0},
        {"port": 8080.0, "bytes": 2500.0},
    ]
    for f in flows:
        scaler.learn_one(f)

    for f in flows:
        scaled = scaler.transform_one(f)
        for val in scaled.values():
            assert 0.0 <= val <= 1.0

    # Signed features (e.g. centered or differential)
    signed_scaler = preprocessing.MaxAbsScaler()
    signed_data = [{"delta": -10.0}, {"delta": 5.0}, {"delta": 20.0}]
    for d in signed_data:
        signed_scaler.learn_one(d)

    scaled_neg = signed_scaler.transform_one({"delta": -10.0})
    assert scaled_neg["delta"] == -0.5
    assert -1.0 <= scaled_neg["delta"] <= 1.0


def test_latency_measurement_separation():
    """Verify that River online OCSVM and baseline Isolation Forest return granular latency fields."""
    model = RiverOnlineOCSVM(nu=0.05, q=0.99)
    flow = {feat: 100.0 for feat in PRIMARY_FEATURES}
    model.warm_up([flow] * 20)
    res = model.evaluate_stream([flow] * 10, [0] * 10)

    assert "avg_latency_per_flow_ms" in res
    assert "avg_inference_latency_ms" in res
    assert "avg_update_latency_ms" in res
    assert res["avg_inference_latency_ms"] >= 0.0
    assert res["avg_update_latency_ms"] >= 0.0
    assert res["avg_latency_per_flow_ms"] >= res["avg_inference_latency_ms"]

    iforest = BaselineIsolationForest(n_estimators=10)
    iforest.train_baseline([flow] * 20)
    if_res = iforest.evaluate_stream([flow] * 10, [0] * 10)
    assert "avg_latency_per_flow_ms" in if_res
    assert "batch_latency_per_flow_ms" in if_res
    assert "batch_throughput_flows_sec" in if_res

