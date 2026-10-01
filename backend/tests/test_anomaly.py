"""Automated unit and integration tests for AI network anomaly detection engine.

Covers feature engineering, warm-up calibration, Isolation Forest training,
score normalization, statistical fallbacks, SQLite persistence, REST endpoints,
and live WebSocket alert streaming. Uses synthetic isolated test data only.
"""

from collections import namedtuple
from datetime import datetime, timedelta, timezone
import json
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.collector import NetworkMetrics, NetworkTrafficCollector
from app.database import Base, get_db
from app.main import app
from app.models import AnomalyEventModel, NetworkMetricModel
from app.schemas import AnomalyEventResponse
from app.services.anomaly import AnomalyDetector, AnomalyEvaluationResult
from app.services.features import NetworkFeatureExtractor, NetworkFeatures
from app.services.monitoring import monitoring_service

# Test database setup with in-memory SQLite
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create fresh SQLite tables before each test and restore state afterwards."""
    app.dependency_overrides[get_db] = override_get_db
    original_session_factory = monitoring_service.session_factory
    monitoring_service.session_factory = TestingSessionLocal
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    monitoring_service.session_factory = original_session_factory



@pytest.fixture
def client():
    """FastAPI TestClient with isolated dependency overrides."""
    return TestClient(app)


# ============================================================================
# 1. Feature Extraction Tests
# ============================================================================


class TestFeatureExtraction:
    """Tests for multi-dimensional telemetry feature engineering."""

    def test_feature_extraction_normal_sample(self):
        extractor = NetworkFeatureExtractor(window_size=20)
        sample = {
            "interface": "eth0",
            "download_mbps": 12.5,
            "upload_mbps": 2.5,
            "packets_received_per_sec": 1200.0,
            "packets_sent_per_sec": 300.0,
            "is_initial_sample": False,
        }
        features = extractor.extract(sample)

        assert features.download_mbps == 12.5
        assert features.upload_mbps == 2.5
        assert features.total_mbps == 15.0
        assert features.total_packets_per_sec == 1500.0
        assert features.upload_download_ratio == pytest.approx(2.5 / (12.5 + 1e-4), rel=1e-3)
        assert features.packet_ratio == pytest.approx(300.0 / (1200.0 + 1e-4), rel=1e-3)
        assert features.bytes_per_packet > 0.0
        assert len(features.to_vector()) == len(NetworkFeatures.FEATURE_NAMES)
        assert features.to_numpy().shape == (1, 15)

    def test_feature_extraction_zero_traffic(self):
        """Idle interface with 0 throughput and 0 packets must not produce NaN or Inf."""
        extractor = NetworkFeatureExtractor()
        sample = {
            "interface": "wlan0",
            "download_mbps": 0.0,
            "upload_mbps": 0.0,
            "packets_received_per_sec": 0.0,
            "packets_sent_per_sec": 0.0,
            "is_initial_sample": False,
        }
        features = extractor.extract(sample)

        assert features.total_mbps == 0.0
        assert features.total_packets_per_sec == 0.0
        assert features.upload_download_ratio == 1.0  # Safe balanced idle ratio
        assert features.packet_ratio == 1.0
        assert features.bytes_per_packet == 0.0
        assert np.all(np.isfinite(features.to_vector()))

    def test_feature_extraction_initial_baseline_sample(self):
        """Initial baseline sample does not corrupt the rolling baseline buffer."""
        extractor = NetworkFeatureExtractor(window_size=10)
        initial_sample = {
            "interface": "eth0",
            "download_mbps": 0.0,
            "upload_mbps": 0.0,
            "is_initial_sample": True,
        }
        features = extractor.extract(initial_sample)
        assert extractor.history_length == 0
        assert features.mbps_deviation == 0.0

    def test_feature_extraction_interface_switch_resets_history(self):
        """Switching monitored interface clears previous adapter's history."""
        extractor = NetworkFeatureExtractor(window_size=10)
        for _ in range(5):
            extractor.extract({"interface": "eth0", "download_mbps": 10.0, "is_initial_sample": False})
        assert extractor.history_length == 5

        # Switch to wlan0
        extractor.extract({"interface": "wlan0", "download_mbps": 2.0, "is_initial_sample": False})
        assert extractor.active_interface == "wlan0"
        assert extractor.history_length == 1

    def test_feature_extraction_rolling_deviations(self):
        """Rolling mean and std accurately track history and compute z-score deviations."""
        extractor = NetworkFeatureExtractor(window_size=10)
        # Feed 10 steady samples at ~5.0 Mbps total
        for _ in range(10):
            extractor.extract({
                "interface": "eth0",
                "download_mbps": 4.0,
                "upload_mbps": 1.0,
                "packets_received_per_sec": 400.0,
                "packets_sent_per_sec": 100.0,
                "is_initial_sample": False,
            })

        # Inject a 10x throughput surge
        surge_sample = {
            "interface": "eth0",
            "download_mbps": 50.0,
            "upload_mbps": 5.0,
            "packets_received_per_sec": 5000.0,
            "packets_sent_per_sec": 500.0,
            "is_initial_sample": False,
        }
        surge_features = extractor.extract(surge_sample)
        assert surge_features.rolling_mean_mbps == pytest.approx(5.0, rel=1e-2)
        assert surge_features.mbps_deviation > 3.0


# ============================================================================
# 2. Anomaly Detector Engine Tests
# ============================================================================


class TestAnomalyDetectorEngine:
    """Tests for Isolation Forest training, warm-up calibration, and scoring."""

    def test_warmup_behavior(self):
        """During warm-up (first 20 samples), detector returns score 0.0 and Normal severity."""
        detector = AnomalyDetector(warmup_samples=20)

        for i in range(15):
            sample = {
                "interface": "eth0",
                "download_mbps": 5.0,
                "upload_mbps": 1.0,
                "packets_received_per_sec": 500.0,
                "packets_sent_per_sec": 100.0,
                "is_initial_sample": False,
            }
            res = detector.evaluate(sample)
            assert not detector.is_warmed_up
            assert res.anomaly_score == 0.0
            assert res.severity == AnomalyDetector.SEVERITY_NORMAL
            assert res.detection_method == "warmup"
            assert not res.is_anomaly

    def test_model_training_and_score_range(self):
        """Detector trains successfully when sufficient samples exist and produces scores in [0.0, 1.0]."""
        detector = AnomalyDetector(warmup_samples=20, min_train_samples=25, random_state=42)

        # Collect 30 normal baseline samples
        rng = np.random.RandomState(42)
        for i in range(30):
            dl = 2.0 + rng.normal(0, 0.2)
            ul = 0.5 + rng.normal(0, 0.05)
            sample = {
                "interface": "eth0",
                "download_mbps": max(0.1, dl),
                "upload_mbps": max(0.05, ul),
                "packets_received_per_sec": max(10, dl * 100),
                "packets_sent_per_sec": max(5, ul * 80),
                "is_initial_sample": False,
            }
            detector.evaluate(sample)

        assert detector.is_warmed_up
        # Train model
        train_success = detector.train()
        assert train_success is True
        assert detector.is_trained is True
        assert detector.status == "active"

        # Evaluate a steady sample
        steady_sample = {
            "interface": "eth0",
            "download_mbps": 2.0,
            "upload_mbps": 0.5,
            "packets_received_per_sec": 200.0,
            "packets_sent_per_sec": 40.0,
            "is_initial_sample": False,
        }
        res_normal = detector.evaluate(steady_sample)
        assert 0.0 <= res_normal.anomaly_score <= 1.0
        assert res_normal.severity == AnomalyDetector.SEVERITY_NORMAL
        assert res_normal.detection_method == "isolation_forest"

    def test_synthetic_throughput_spike_detection(self):
        """Massive throughput burst is flagged as Unusual Traffic or High Anomaly."""
        detector = AnomalyDetector(warmup_samples=20, min_train_samples=25, random_state=42)

        # Baseline training on ~2 Mbps traffic
        for _ in range(30):
            detector.evaluate({
                "interface": "eth0",
                "download_mbps": 2.0,
                "upload_mbps": 0.5,
                "packets_received_per_sec": 200.0,
                "packets_sent_per_sec": 50.0,
                "is_initial_sample": False,
            })
        detector.train()

        # Inject extreme spike
        spike_sample = {
            "interface": "eth0",
            "download_mbps": 95.0,
            "upload_mbps": 40.0,
            "packets_received_per_sec": 9500.0,
            "packets_sent_per_sec": 4000.0,
            "is_initial_sample": False,
        }
        res_spike = detector.evaluate(spike_sample)
        assert res_spike.anomaly_score >= AnomalyDetector.THRESHOLD_UNUSUAL
        assert res_spike.severity in (AnomalyDetector.SEVERITY_UNUSUAL, AnomalyDetector.SEVERITY_HIGH)
        assert res_spike.is_anomaly is True
        assert "surge" in res_spike.explanation.lower() or "deviates" in res_spike.explanation.lower()

    def test_reproducibility_with_fixed_seed(self):
        """Two detectors initialized with the same random seed produce identical scores on identical input."""
        det1 = AnomalyDetector(warmup_samples=20, min_train_samples=20, random_state=42)
        det2 = AnomalyDetector(warmup_samples=20, min_train_samples=20, random_state=42)

        samples = [
            {
                "interface": "eth0",
                "download_mbps": 1.0 + (i % 3) * 0.5,
                "upload_mbps": 0.2 + (i % 2) * 0.1,
                "packets_received_per_sec": 100.0,
                "packets_sent_per_sec": 20.0,
                "is_initial_sample": False,
            }
            for i in range(25)
        ]

        for s in samples:
            det1.evaluate(s)
            det2.evaluate(s)

        det1.train()
        det2.train()

        test_sample = {
            "interface": "eth0",
            "download_mbps": 15.0,
            "upload_mbps": 3.0,
            "packets_received_per_sec": 1500.0,
            "packets_sent_per_sec": 300.0,
            "is_initial_sample": False,
        }
        res1 = det1.evaluate(test_sample)
        res2 = det2.evaluate(test_sample)

        assert res1.anomaly_score == res2.anomaly_score
        assert res1.severity == res2.severity


# ============================================================================
# 3. Database Persistence Tests
# ============================================================================


class TestAnomalyDatabasePersistence:
    """Tests for SQLite anomaly events table schema and queries."""

    def test_persist_and_query_anomaly_event(self):
        db = TestingSessionLocal()
        event = AnomalyEventModel(
            timestamp=datetime.now(timezone.utc),
            interface="eth0",
            anomaly_score=0.88,
            severity="High Anomaly",
            detection_method="isolation_forest",
            metrics_snapshot=json.dumps({"download_mbps": 85.0, "upload_mbps": 20.0}),
            explanation="High Anomaly: Download throughput surge to 85.0 Mbps.",
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        assert event.id is not None
        queried = db.query(AnomalyEventModel).filter_by(id=event.id).first()
        assert queried is not None
        assert queried.interface == "eth0"
        assert queried.anomaly_score == 0.88
        assert queried.severity == "High Anomaly"

        # Schema deserialization
        resp = AnomalyEventResponse.model_validate(queried)
        assert resp.metrics_snapshot["download_mbps"] == 85.0
        db.close()


# ============================================================================
# 4. REST API Endpoint Tests
# ============================================================================


class TestAnomalyApiEndpoints:
    """Tests for GET /api/v1/anomalies, /latest, and /summary."""

    def test_get_anomalies_empty(self, client):
        res = client.get("/api/v1/anomalies")
        assert res.status_code == 200
        data = res.json()
        assert data["total_returned"] == 0
        assert data["events"] == []

    def test_get_latest_anomaly_empty(self, client):
        res = client.get("/api/v1/anomalies/latest")
        assert res.status_code == 200
        assert res.json() is None

    def test_get_anomalies_with_data_and_filtering(self, client):
        db = TestingSessionLocal()
        now = datetime.now(timezone.utc)
        e1 = AnomalyEventModel(
            timestamp=now - timedelta(seconds=20),
            interface="eth0",
            anomaly_score=0.65,
            severity="Unusual Traffic",
            detection_method="isolation_forest",
            metrics_snapshot="{}",
            explanation="Unusual traffic volume",
        )
        e2 = AnomalyEventModel(
            timestamp=now - timedelta(seconds=10),
            interface="wlan0",
            anomaly_score=0.92,
            severity="High Anomaly",
            detection_method="isolation_forest",
            metrics_snapshot="{}",
            explanation="High packet surge",
        )
        db.add_all([e1, e2])
        db.commit()
        db.close()

        # Query all
        res = client.get("/api/v1/anomalies?limit=10")
        assert res.status_code == 200
        data = res.json()
        assert data["total_returned"] == 2
        assert data["events"][0]["interface"] == "wlan0"  # Ordered desc

        # Filter by interface
        res_iface = client.get("/api/v1/anomalies?interface=eth0")
        assert res_iface.status_code == 200
        data_iface = res_iface.json()
        assert data_iface["total_returned"] == 1
        assert data_iface["events"][0]["interface"] == "eth0"

        # Filter by severity
        res_sev = client.get("/api/v1/anomalies?severity=High%20Anomaly")
        assert res_sev.status_code == 200
        assert res_sev.json()["total_returned"] == 1

        # Test latest
        res_latest = client.get("/api/v1/anomalies/latest")
        assert res_latest.status_code == 200
        assert res_latest.json()["severity"] == "High Anomaly"

    def test_get_anomaly_summary(self, client):
        db = TestingSessionLocal()
        e1 = AnomalyEventModel(
            timestamp=datetime.now(timezone.utc),
            interface="eth0",
            anomaly_score=0.65,
            severity="Unusual Traffic",
            detection_method="isolation_forest",
            metrics_snapshot="{}",
            explanation="Unusual traffic",
        )
        db.add(e1)
        db.commit()
        db.close()

        res = client.get("/api/v1/anomalies/summary")
        assert res.status_code == 200
        data = res.json()
        assert data["total_anomalies"] == 1
        assert data["unusual_traffic_count"] == 1
        assert data["high_anomaly_count"] == 0
        assert data["latest_anomaly"] is not None
        assert "model_status" in data


# ============================================================================
# 5. WebSocket Integration Tests
# ============================================================================


class TestAnomalyWebSocketIntegration:
    """Tests that WebSocket streams enriched metric updates and anomaly alerts."""

    def test_websocket_broadcasts_enriched_anomaly_field(self, client):
        # Inject sample directly into monitoring service
        monitoring_service.active_interface = "eth0"
        sample_metrics = NetworkMetrics(
            interface_name="eth0",
            timestamp=1000.0,
            elapsed_seconds=1.0,
            upload_mbps=1.2,
            download_mbps=5.5,
            packets_sent_per_sec=20.0,
            packets_recv_per_sec=80.0,
            session_bytes_sent=100_000,
            session_bytes_recv=500_000,
            session_transferred_mb=0.6,
            cumulative_bytes_sent=100_000,
            cumulative_bytes_recv=500_000,
            cumulative_packets_sent=100,
            cumulative_packets_recv=500,
            cumulative_transferred_mb=0.6,
            is_initial_sample=False,
        )


        with client.websocket_connect("/ws/metrics") as ws:
            # Service broadcasts a metric update with anomaly metadata
            res = monitoring_service.anomaly_detector.evaluate(sample_metrics)
            import asyncio
            asyncio.run(monitoring_service._broadcast_metric(sample_metrics, 1, res))

            msg = ws.receive_text()
            payload = json.loads(msg)
            if payload.get("type") == "initial_state":
                msg = ws.receive_text()
                payload = json.loads(msg)
            assert payload["type"] == "metric_update"
            assert "anomaly" in payload["data"]
            assert "score" in payload["data"]["anomaly"]
            assert "severity" in payload["data"]["anomaly"]
            assert "method" in payload["data"]["anomaly"]
