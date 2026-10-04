"""Automated test suite for dataset validation, schema detection, and the UNSW-NB15 adapter.

Verifies:
1. Native NetFlow schema validation (NF-UNSW-NB15).
2. UNSW-NB15 testing set adapter (sbytes, dbytes, dur, proto, label).
3. Protocol string-to-IANA numeric mapping.
4. Duration seconds-to-milliseconds unit conversion.
5. Byte direction semantics (sbytes -> IN_BYTES, dbytes -> OUT_BYTES).
6. Missing required feature rejection (no silent defaulting to zero).
7. Duplicate column detection.
8. Empty or malformed dataset rejection.
9. Strict label isolation (labels strictly excluded from feature vectors).
10. Small dataset safeguards (adaptive scaling and adjustment reporting).
11. End-to-end experiment execution on adapted dataset.
12. FastAPI dataset upload endpoint validation.
"""

import csv
import io
import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.pool import StaticPool
from app.database import Base, get_db, init_db
from app.main import app
from app.models import ResearchDatasetModel, ResearchExperimentModel
from app.services.research.dataset_service import (
    DatasetService,
    DatasetValidationError,
    DatasetSchemaType,
    PRIMARY_FEATURES,
    IANA_PROTOCOL_MAP,
    parse_protocol,
    validate_ipv4,
)
from app.services.research.experiment_runner import ExperimentRunner
from app.services.research.online_ocsvm import RiverOnlineOCSVM
from app.services.research.baseline_iforest import BaselineIsolationForest


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def service(temp_dir):
    return DatasetService(data_dir=temp_dir)


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
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
# 1. Protocol Mapping and Conversion Tests
# ============================================================================


def test_protocol_iana_mapping():
    """Verify standard protocol string names are correctly converted to IANA numeric values."""
    assert parse_protocol("tcp") == 6
    assert parse_protocol("TCP") == 6
    assert parse_protocol("udp") == 17
    assert parse_protocol("UDP") == 17
    assert parse_protocol("icmp") == 1
    assert parse_protocol("arp") == 0
    assert parse_protocol("ospf") == 89
    assert parse_protocol("gre") == 47
    assert parse_protocol("ipv6") == 41
    assert parse_protocol("sctp") == 132
    assert parse_protocol("unas") == 255


def test_protocol_numeric_inputs():
    """Verify numeric protocol inputs (integers, numeric strings) are properly preserved."""
    assert parse_protocol(6) == 6
    assert parse_protocol("6") == 6
    assert parse_protocol(17.0) == 17
    assert parse_protocol("17") == 17
    assert parse_protocol("0") == 0
    assert parse_protocol("255") == 255


def test_protocol_unknown_fallback():
    """Verify unknown or missing protocol strings fall back safely without crashing."""
    assert parse_protocol(None) == 6  # default
    assert parse_protocol("") == 6
    assert parse_protocol("unknown_custom_protocol_xyz") == 0


# ============================================================================
# 2. IP Address Validation Tests
# ============================================================================


def test_validate_ipv4():
    """Verify strict IPv4 validation correctly identifies valid and invalid addresses."""
    assert validate_ipv4("192.168.1.1") is True
    assert validate_ipv4("10.0.0.1") is True
    assert validate_ipv4("127.0.0.1") is True
    assert validate_ipv4(3232235777) is True
    assert validate_ipv4("3232235777") is True

    # Invalid IPs
    assert validate_ipv4("not_an_ip") is False
    assert validate_ipv4("999.999.999.999") is False
    assert validate_ipv4("") is False
    assert validate_ipv4(None) is False
    assert validate_ipv4(-5) is False


# ============================================================================
# 3. Schema Detection & Feature Mapping Tests
# ============================================================================


def test_detect_native_netflow_schema(service):
    """Verify native NetFlow v9 / NF-UNSW-NB15 schema is detected and not marked adapted."""
    header = [
        "IPV4_SRC_ADDR",
        "IPV4_DST_ADDR",
        "L4_SRC_PORT",
        "L4_DST_PORT",
        "PROTOCOL",
        "IN_BYTES",
        "OUT_BYTES",
        "FLOW_DURATION_MILLISECONDS",
        "Label",
    ]
    schema_type, mapping, is_adapted, notes = service.detect_schema_and_mapping(header)

    assert schema_type == DatasetSchemaType.NATIVE_NETFLOW
    assert is_adapted is False
    assert notes is None
    assert mapping["IN_BYTES"] == "IN_BYTES"
    assert mapping["FLOW_DURATION_MILLISECONDS"] == "FLOW_DURATION_MILLISECONDS"
    assert mapping["LABEL"] == "Label"


def test_detect_adapted_unsw_nb15_schema(service):
    """Verify official UNSW-NB15 testing CSV columns trigger the adapter with explicit direction semantics."""
    header = [
        "id",
        "dur",
        "proto",
        "service",
        "state",
        "spkts",
        "dpkts",
        "sbytes",
        "dbytes",
        "rate",
        "sttl",
        "dttl",
        "attack_cat",
        "label",
    ]
    schema_type, mapping, is_adapted, notes = service.detect_schema_and_mapping(header)

    assert schema_type == DatasetSchemaType.ADAPTED_UNSW_NB15
    assert is_adapted is True
    assert notes is not None
    assert "Official UNSW-NB15 testing-set adaptation" in notes
    assert "NOT equivalent to native 8-feature NetFlow schema" in notes

    # Check byte direction semantics
    assert mapping["IN_BYTES"] == "sbytes"
    assert mapping["OUT_BYTES"] == "dbytes"
    assert mapping["FLOW_DURATION_MILLISECONDS"] == "dur"
    assert mapping["PROTOCOL"] == "proto"
    assert mapping["LABEL"] == "label"


def test_reject_missing_required_features(service):
    """Verify dataset missing critical features is rejected with an informative error rather than defaulting to zero."""
    # Missing duration and out_bytes
    header = ["ipv4_src_addr", "ipv4_dst_addr", "l4_src_port", "l4_dst_port", "protocol", "in_bytes", "label"]
    with pytest.raises(DatasetValidationError) as exc_info:
        service.detect_schema_and_mapping(header)

    err = str(exc_info.value)
    assert "Incompatible dataset schema" in err
    assert "OUT_BYTES" in err or "FLOW_DURATION_MILLISECONDS" in err


def test_reject_missing_label(service):
    """Verify dataset with no label column is rejected."""
    header = [
        "IPV4_SRC_ADDR", "IPV4_DST_ADDR", "L4_SRC_PORT", "L4_DST_PORT",
        "PROTOCOL", "IN_BYTES", "OUT_BYTES", "FLOW_DURATION_MILLISECONDS"
    ]
    with pytest.raises(DatasetValidationError) as exc_info:
        service.detect_schema_and_mapping(header)
    assert "missing a required label column" in str(exc_info.value).lower()


def test_reject_duplicate_columns(service):
    """Verify CSV with duplicate column names is strictly rejected."""
    header = ["dur", "proto", "sbytes", "dbytes", "label", "proto"]
    with pytest.raises(DatasetValidationError) as exc_info:
        service.detect_schema_and_mapping(header)
    assert "duplicate or ambiguous columns" in str(exc_info.value).lower()


def test_reject_empty_header(service):
    """Verify empty header is rejected."""
    with pytest.raises(DatasetValidationError):
        service.detect_schema_and_mapping([])


# ============================================================================
# 4. Duration & Byte Conversion and Label Isolation Tests
# ============================================================================


def test_unsw_adapter_duration_conversion(service):
    """Verify official UNSW-NB15 duration (seconds) is accurately converted to milliseconds (* 1000)."""
    mapping = {
        "IN_BYTES": "sbytes",
        "OUT_BYTES": "dbytes",
        "FLOW_DURATION_MILLISECONDS": "dur",
        "PROTOCOL": "proto",
        "LABEL": "label",
    }
    # Official UNSW-NB15 has dur in seconds: e.g. 0.000011 seconds = 0.011 ms, 0.583 seconds = 583.0 ms
    row = {
        "dur": "0.000011",
        "proto": "tcp",
        "sbytes": "200",
        "dbytes": "400",
        "label": "0",
    }
    features, label = service.parse_flow_row(row, mapping, schema_type=DatasetSchemaType.ADAPTED_UNSW_NB15)

    assert pytest.approx(features["FLOW_DURATION_MILLISECONDS"], rel=1e-3) == 0.011
    assert features["IN_BYTES"] == 200.0
    assert features["OUT_BYTES"] == 400.0
    assert features["PROTOCOL"] == 6.0
    assert features["IPV4_SRC_ADDR"] == 0.0  # surrogate
    assert label == 0


def test_unsw_adapter_longer_duration(service):
    """Verify longer durations in seconds convert correctly to ms."""
    mapping = {
        "IN_BYTES": "sbytes",
        "OUT_BYTES": "dbytes",
        "FLOW_DURATION_MILLISECONDS": "dur",
        "PROTOCOL": "proto",
        "LABEL": "label",
    }
    row = {
        "dur": "1.25",
        "proto": "udp",
        "sbytes": "1000",
        "dbytes": "5000",
        "label": "1",
    }
    features, label = service.parse_flow_row(row, mapping, schema_type=DatasetSchemaType.ADAPTED_UNSW_NB15)
    assert pytest.approx(features["FLOW_DURATION_MILLISECONDS"], rel=1e-3) == 1250.0
    assert features["PROTOCOL"] == 17.0
    assert label == 1


def test_strict_label_isolation(service):
    """CRITICAL: Verify labels are completely absent from the feature vector."""
    mapping = {
        "IN_BYTES": "sbytes",
        "OUT_BYTES": "dbytes",
        "FLOW_DURATION_MILLISECONDS": "dur",
        "PROTOCOL": "proto",
        "LABEL": "label",
    }
    row = {
        "dur": "0.5",
        "proto": "tcp",
        "sbytes": "500",
        "dbytes": "1200",
        "label": "1",
        "attack_cat": "Exploits",
    }
    features, label = service.parse_flow_row(row, mapping, schema_type=DatasetSchemaType.ADAPTED_UNSW_NB15)

    # Label keys must NEVER exist in features dictionary
    assert "label" not in features
    assert "Label" not in features
    assert "attack" not in features
    assert "attack_cat" not in features
    assert "is_anomaly" not in features
    assert set(features.keys()) == set(PRIMARY_FEATURES)


# ============================================================================
# 5. Dataset Inspection and File Validation Tests
# ============================================================================


def test_inspect_adapted_unsw_dataset_file(service, temp_dir):
    """Verify inspection of an adapted UNSW-NB15 CSV file."""
    csv_path = os.path.join(temp_dir, "test_unsw.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "dur", "proto", "sbytes", "dbytes", "label"])
        # 15 benign flows
        for i in range(15):
            writer.writerow([i + 1, 0.05, "tcp", 1000, 2000, 0])
        # 5 attack flows
        for i in range(5):
            writer.writerow([i + 16, 0.01, "udp", 50, 0, 1])

    stats = service.inspect_dataset_file(csv_path)

    assert stats["total_flows"] == 20
    assert stats["benign_flows"] == 15
    assert stats["attack_flows"] == 5
    assert stats["schema_type"] == DatasetSchemaType.ADAPTED_UNSW_NB15
    assert stats["is_adapted"] is True
    assert "Adapted UNSW-NB15" in stats["validation_status"]
    assert stats["duration_unit"] == "seconds (converted *1000 to ms)"


def test_inspect_rejects_empty_csv(service, temp_dir):
    """Verify completely empty file is rejected."""
    empty_path = os.path.join(temp_dir, "empty.csv")
    with open(empty_path, "w", encoding="utf-8") as f:
        pass  # 0 bytes

    with pytest.raises(DatasetValidationError) as exc_info:
        service.inspect_dataset_file(empty_path)
    assert "0 bytes" in str(exc_info.value)


def test_inspect_rejects_header_only_csv(service, temp_dir):
    """Verify CSV with header but zero data rows is rejected."""
    header_only_path = os.path.join(temp_dir, "header_only.csv")
    with open(header_only_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["dur", "proto", "sbytes", "dbytes", "label"])

    with pytest.raises(DatasetValidationError) as exc_info:
        service.inspect_dataset_file(header_only_path)
    assert "0 data rows" in str(exc_info.value)


# ============================================================================
# 6. Small Dataset Safeguards and Experiment Partitioning
# ============================================================================


def test_small_dataset_safeguard_downscaling(service, temp_dir):
    """Verify requested counts that exceed available records are safely reduced and reported."""
    csv_path = os.path.join(temp_dir, "small_unsw.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "dur", "proto", "sbytes", "dbytes", "label"])
        # 60 benign flows
        for i in range(60):
            writer.writerow([i + 1, 0.05, "tcp", 1000, 2000, 0])
        # 30 attack flows
        for i in range(30):
            writer.writerow([i + 61, 0.01, "udp", 50, 0, 1])

    # Request paper defaults: 1,000 scaler init, 100,000 warmup, 50,000 eval
    # Small dataset has only 60 benign flows!
    split_data = service.prepare_experiment_data(
        file_path=csv_path,
        scaler_init_count=1000,
        warmup_count=100000,
        eval_count=50000,
        random_seed=42,
    )

    # Safeguards must adjust counts dynamically
    assert split_data["config_adjusted"] is True
    assert "reduced" in split_data["adjustment_reason"].lower()
    assert split_data["actual_scaler_init_count"] < 60
    assert split_data["actual_warmup_count"] < 60
    assert split_data["actual_eval_count"] > 0
    # Equal benign and attack in evaluation
    assert split_data["eval_benign_count"] == split_data["eval_attack_count"]


def test_small_dataset_rejection_when_too_few_benign(service, temp_dir):
    """Verify datasets with fewer than 10 benign samples are rejected."""
    csv_path = os.path.join(temp_dir, "tiny.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["dur", "proto", "sbytes", "dbytes", "label"])
        for i in range(5):  # only 5 benign
            writer.writerow([0.05, "tcp", 100, 200, 0])
        for i in range(5):
            writer.writerow([0.01, "udp", 10, 0, 1])

    with pytest.raises(DatasetValidationError) as exc_info:
        service.prepare_experiment_data(csv_path)
    assert "too few benign samples" in str(exc_info.value).lower()


# ============================================================================
# 7. End-to-End Model Execution on Adapted Dataset
# ============================================================================


def test_river_ocsvm_runs_on_adapted_dataset(service, temp_dir):
    """Verify River Online One-Class SVM successfully trains and evaluates on an adapted dataset."""
    csv_path = os.path.join(temp_dir, "eval_unsw.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["dur", "proto", "sbytes", "dbytes", "label"])
        for i in range(80):
            writer.writerow([0.05, "tcp", 1000 + i * 10, 2000, 0])
        for i in range(30):
            writer.writerow([0.001, "udp", 44, 0, 1])

    split_data = service.prepare_experiment_data(
        file_path=csv_path,
        scaler_init_count=10,
        warmup_count=30,
        random_seed=42,
    )

    model = RiverOnlineOCSVM(nu=0.05, q=0.99, learning_rate=0.1)
    model.initialize_scaler(split_data["scaler_init_flows"])
    model.warm_up(split_data["warmup_flows"])

    results = model.evaluate_stream(
        split_data["eval_flows"],
        split_data["eval_labels"],
    )

    assert "accuracy" in results
    assert "f1_score" in results
    assert "confusion_matrix" in results
    cm = results["confusion_matrix"]
    assert cm["tp"] + cm["tn"] + cm["fp"] + cm["fn"] == len(split_data["eval_flows"])


def test_iforest_runs_on_adapted_dataset(service, temp_dir):
    """Verify Baseline Isolation Forest successfully evaluates on an adapted dataset."""
    csv_path = os.path.join(temp_dir, "iforest_unsw.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["dur", "proto", "sbytes", "dbytes", "label"])
        for i in range(80):
            writer.writerow([0.05, "tcp", 1000 + i * 10, 2000, 0])
        for i in range(30):
            writer.writerow([0.001, "udp", 44, 0, 1])

    split_data = service.prepare_experiment_data(
        file_path=csv_path,
        scaler_init_count=10,
        warmup_count=30,
        random_seed=42,
    )

    iforest = BaselineIsolationForest(contamination=0.05, n_estimators=20)
    iforest.train_baseline(split_data["warmup_flows"])
    results = iforest.evaluate_stream(split_data["eval_flows"], split_data["eval_labels"])

    assert "accuracy" in results
    cm = results["confusion_matrix"]
    assert cm["tp"] + cm["tn"] + cm["fp"] + cm["fn"] == len(split_data["eval_flows"])


# ============================================================================
# 8. API Endpoint Validation Tests
# ============================================================================


def test_api_upload_rejects_invalid_csv(client):
    """Verify FastAPI endpoint rejects missing required features with HTTP 400."""
    invalid_csv = "col1,col2,col3\n1,2,3\n"
    response = client.post(
        "/api/v1/research/datasets/upload",
        files={"file": ("invalid.csv", io.BytesIO(invalid_csv.encode("utf-8")), "text/csv")},
        data={"name": "Bad Dataset"},
    )
    assert response.status_code == 400
    assert "missing a required label column" in response.json()["detail"].lower()

    # Also test CSV with label but missing required features
    invalid_features_csv = "col1,col2,label\n1,2,0\n"
    response2 = client.post(
        "/api/v1/research/datasets/upload",
        files={"file": ("invalid2.csv", io.BytesIO(invalid_features_csv.encode("utf-8")), "text/csv")},
        data={"name": "Bad Dataset 2"},
    )
    assert response2.status_code == 400
    assert "incompatible dataset schema" in response2.json()["detail"].lower()


def test_api_upload_accepts_adapted_unsw_nb15(client):
    """Verify FastAPI endpoint accepts valid adapted UNSW-NB15 CSV and sets is_adapted=True."""
    lines = ["id,dur,proto,sbytes,dbytes,label"]
    for i in range(20):
        lines.append(f"{i+1},0.05,tcp,1000,2000,0")
    for i in range(10):
        lines.append(f"{i+21},0.001,udp,44,0,1")
    csv_content = "\n".join(lines) + "\n"

    response = client.post(
        "/api/v1/research/datasets/upload",
        files={"file": ("unsw_test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        data={"name": "UNSW Testing Set Test", "version": "UNSW-NB15-Testing-Set"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "UNSW Testing Set Test"
    assert data["is_adapted"] is True
    assert data["schema_type"] == DatasetSchemaType.ADAPTED_UNSW_NB15
    assert data["adaptation_notes"] is not None
