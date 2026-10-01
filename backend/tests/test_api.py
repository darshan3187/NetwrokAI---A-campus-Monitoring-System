"""Automated tests for FastAPI endpoints, database persistence, and WebSocket streaming.

Uses an isolated in-memory SQLite database and mocked collector inputs to guarantee
fast, deterministic test execution independent of live network traffic.
"""

from collections import namedtuple
from datetime import datetime, timedelta, timezone
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.collector import NetworkMetrics, NetworkTrafficCollector
from app.database import Base, get_db
from app.main import app
from app.models import NetworkMetricModel
from app.services.monitoring import monitoring_service

# Mock network counter namedtuple
MockNetIO = namedtuple(
    "MockNetIO",
    [
        "bytes_sent",
        "bytes_recv",
        "packets_sent",
        "packets_recv",
        "errin",
        "errout",
        "dropin",
        "dropout",
    ],
    defaults=(0, 0, 0, 0),
)

# Test in-memory SQLite database setup
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


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create fresh database tables before each test and drop them afterwards."""
    app.dependency_overrides[get_db] = override_get_db
    original_session_factory = monitoring_service.session_factory
    monitoring_service.session_factory = TestingSessionLocal
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    monitoring_service.session_factory = original_session_factory



@pytest.fixture
def mock_collector():
    """Create a collector with synthetic predictable interface statistics."""
    mock_data = {
        "eth0": MockNetIO(
            bytes_sent=10_000_000,
            bytes_recv=20_000_000,
            packets_sent=5000,
            packets_recv=10000,
        ),
        "wlan0": MockNetIO(
            bytes_sent=30_000_000,
            bytes_recv=40_000_000,
            packets_sent=15000,
            packets_recv=20000,
        ),
    }
    clock_time = 1000.0

    collector = NetworkTrafficCollector(
        io_counters_fn=lambda pernic=True: mock_data,
        time_fn=lambda: clock_time,
        wall_time_fn=lambda: clock_time,
    )
    return collector


@pytest.fixture
def client(mock_collector):
    """TestClient with mocked collector injected into the monitoring service."""
    original_collector = monitoring_service.collector
    monitoring_service.collector = mock_collector
    monitoring_service.active_interface = "eth0"

    with TestClient(app) as test_client:
        yield test_client

    monitoring_service.collector = original_collector


class TestSystemEndpoints:
    """Test suite for system health and interface discovery endpoints."""

    def test_health_endpoint(self, client):
        """Verify /api/v1/health returns ok status and database connectivity."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"
        assert "monitoring" in data
        assert "timestamp" in data

    def test_interfaces_endpoint(self, client):
        """Verify /api/v1/interfaces lists mocked interfaces and their details."""
        response = client.get("/api/v1/interfaces")
        assert response.status_code == 200
        data = response.json()
        assert "interfaces" in data
        assert "eth0" in data["interfaces"]
        assert "wlan0" in data["interfaces"]
        assert data["count"] == 2
        assert len(data["details"]) == 2
        eth_detail = next(d for d in data["details"] if d["name"] == "eth0")
        assert eth_detail["bytes_sent"] == 10_000_000
        assert eth_detail["bytes_recv"] == 20_000_000


class TestTelemetryEndpoints:
    """Test suite for live telemetry, history, and session summaries."""

    def test_current_metrics_endpoint(self, client):
        """Verify /api/v1/metrics/current returns valid telemetry payload."""
        # Inject synthetic metrics into the service
        monitoring_service._latest_metrics = NetworkMetrics(
            interface_name="eth0",
            timestamp=datetime.now(timezone.utc).timestamp(),
            elapsed_seconds=1.0,
            upload_mbps=1.234,
            download_mbps=5.678,
            packets_sent_per_sec=120.0,
            packets_recv_per_sec=340.0,
            session_bytes_sent=154250,
            session_bytes_recv=709750,
            session_transferred_mb=0.824,
            cumulative_bytes_sent=10_000_000,
            cumulative_bytes_recv=20_000_000,
            cumulative_packets_sent=5000,
            cumulative_packets_recv=10000,
            cumulative_transferred_mb=28.61,
            is_initial_sample=False,
        )

        response = client.get("/api/v1/metrics/current")
        assert response.status_code == 200
        data = response.json()
        assert data["interface"] == "eth0"
        assert data["upload_mbps"] == 1.234
        assert data["download_mbps"] == 5.678
        assert data["packets_sent_per_sec"] == 120.0
        assert data["packets_received_per_sec"] == 340.0
        assert data["session_transferred_mb"] == 0.824

    def test_history_empty(self, client):
        """Verify /api/v1/metrics/history returns empty list when no data is stored."""
        response = client.get("/api/v1/metrics/history")
        assert response.status_code == 200
        data = response.json()
        assert data["total_returned"] == 0
        assert data["metrics"] == []

    def test_history_with_records_and_limit(self, client):
        """Verify historical querying returns persisted records and respects limit."""
        db = TestingSessionLocal()
        now = datetime.now(timezone.utc)
        # Seed 5 sample records
        for i in range(5):
            rec = NetworkMetricModel(
                timestamp=now - timedelta(seconds=i * 10),
                interface="eth0",
                upload_mbps=float(i),
                download_mbps=float(i * 2),
                packets_sent_per_sec=10.0 * i,
                packets_received_per_sec=20.0 * i,
                cumulative_sent_mb=10.0,
                cumulative_received_mb=20.0,
                session_transferred_mb=float(i) * 0.5,
            )
            db.add(rec)
        db.commit()
        db.close()

        # Query with limit 3
        response = client.get("/api/v1/metrics/history?limit=3")
        assert response.status_code == 200
        data = response.json()
        assert data["total_returned"] == 3
        assert len(data["metrics"]) == 3
        # Ensure ordering is descending by timestamp
        assert data["metrics"][0]["upload_mbps"] == 0.0  # Most recent (now - 0s)
        assert data["metrics"][1]["upload_mbps"] == 1.0

    def test_history_filter_by_interface(self, client):
        """Verify historical records can be filtered by interface name."""
        db = TestingSessionLocal()
        now = datetime.now(timezone.utc)
        db.add(
            NetworkMetricModel(
                timestamp=now,
                interface="eth0",
                upload_mbps=1.0,
                download_mbps=2.0,
                packets_sent_per_sec=10.0,
                packets_received_per_sec=20.0,
                cumulative_sent_mb=5.0,
                cumulative_received_mb=5.0,
                session_transferred_mb=0.1,
            )
        )
        db.add(
            NetworkMetricModel(
                timestamp=now,
                interface="wlan0",
                upload_mbps=5.0,
                download_mbps=10.0,
                packets_sent_per_sec=50.0,
                packets_received_per_sec=100.0,
                cumulative_sent_mb=15.0,
                cumulative_received_mb=15.0,
                session_transferred_mb=0.5,
            )
        )
        db.commit()
        db.close()

        # Filter by wlan0
        response = client.get("/api/v1/metrics/history?interface=wlan0")
        assert response.status_code == 200
        data = response.json()
        assert data["total_returned"] == 1
        assert data["metrics"][0]["interface"] == "wlan0"

    def test_history_invalid_query_parameters(self, client):
        """Verify validation errors on invalid historical query arguments."""
        # start_time > end_time
        start = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        end = datetime.now(timezone.utc).isoformat()
        response = client.get("/api/v1/metrics/history", params={"start_time": start, "end_time": end})
        assert response.status_code == 400
        assert "start_time must be earlier than" in response.json()["detail"]

        # limit < 1 (FastAPI validation)
        res_limit = client.get("/api/v1/metrics/history?limit=0")
        assert res_limit.status_code == 422

    def test_summary_endpoint(self, client):
        """Verify /api/v1/summary provides aggregated session and peak statistics."""
        monitoring_service._latest_metrics = NetworkMetrics(
            interface_name="eth0",
            timestamp=datetime.now(timezone.utc).timestamp(),
            elapsed_seconds=1.0,
            upload_mbps=2.5,
            download_mbps=8.0,
            packets_sent_per_sec=50.0,
            packets_recv_per_sec=100.0,
            session_bytes_sent=500_000,
            session_bytes_recv=1_000_000,
            session_transferred_mb=1.43,
            cumulative_bytes_sent=10_485_760,
            cumulative_bytes_recv=20_971_520,
            cumulative_packets_sent=5000,
            cumulative_packets_recv=10000,
            cumulative_transferred_mb=30.0,
            is_initial_sample=False,
        )
        monitoring_service._peak_upload_mbps = 5.0
        monitoring_service._peak_download_mbps = 12.0
        monitoring_service._session_sample_count = 10

        response = client.get("/api/v1/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["interface"] == "eth0"
        assert data["current_upload_mbps"] == 2.5
        assert data["current_download_mbps"] == 8.0
        assert data["peak_upload_mbps"] == 5.0
        assert data["peak_download_mbps"] == 12.0
        assert data["session_samples_collected"] == 10


class TestMonitoringControlAndPersistence:
    """Test suite for monitoring lifecycle controls and database persistence."""

    def test_start_monitoring_invalid_interface(self, client):
        """Verify starting monitoring on an invalid interface returns 404."""
        response = client.post(
            "/api/v1/monitoring/start",
            json={"interface": "nonexistent_interface_xyz", "interval_seconds": 1.0},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_monitoring_service_lifecycle(self, mock_collector):
        """Verify starting and stopping monitoring service manages tasks properly."""
        monitoring_service.collector = mock_collector
        assert monitoring_service._is_running is False

        await monitoring_service.start(interface="eth0", interval=0.1)
        assert monitoring_service._is_running is True
        assert monitoring_service.active_interface == "eth0"
        assert monitoring_service._task is not None

        # Redundant start does not create duplicate tasks
        existing_task = monitoring_service._task
        await monitoring_service.start(interface="eth0", interval=0.1)
        assert monitoring_service._task is existing_task

        await monitoring_service.stop()
        assert monitoring_service._is_running is False
        assert monitoring_service._task is None

    @pytest.mark.asyncio
    async def test_database_persistence(self):
        """Verify that _persist_metric correctly writes NetworkMetricModel to SQLite."""
        sample_metrics = NetworkMetrics(
            interface_name="eth0",
            timestamp=datetime.now(timezone.utc).timestamp(),
            elapsed_seconds=1.0,
            upload_mbps=3.14,
            download_mbps=6.28,
            packets_sent_per_sec=42.0,
            packets_recv_per_sec=84.0,
            session_bytes_sent=1000,
            session_bytes_recv=2000,
            session_transferred_mb=0.003,
            cumulative_bytes_sent=10_485_760,
            cumulative_bytes_recv=20_971_520,
            cumulative_packets_sent=100,
            cumulative_packets_recv=200,
            cumulative_transferred_mb=30.0,
            is_initial_sample=False,
        )

        record_id = await monitoring_service._persist_metric(sample_metrics)
        assert record_id is not None

        # Verify entry exists in DB
        db = TestingSessionLocal()
        record = db.query(NetworkMetricModel).filter(NetworkMetricModel.id == record_id).first()
        assert record is not None
        assert record.interface == "eth0"
        assert record.upload_mbps == 3.14
        assert record.download_mbps == 6.28
        assert record.packets_sent_per_sec == 42.0
        assert record.packets_received_per_sec == 84.0
        db.close()


class TestWebSocketStream:
    """Test suite for real-time WebSocket telemetry streaming."""

    def test_websocket_connection_and_payload(self, client):
        """Verify WebSocket accepts connection and receives properly structured JSON."""
        # Pre-set latest metrics so client receives initial state on connect
        monitoring_service._latest_metrics = NetworkMetrics(
            interface_name="eth0",
            timestamp=datetime.now(timezone.utc).timestamp(),
            elapsed_seconds=1.0,
            upload_mbps=4.5,
            download_mbps=9.0,
            packets_sent_per_sec=60.0,
            packets_recv_per_sec=120.0,
            session_bytes_sent=200_000,
            session_bytes_recv=400_000,
            session_transferred_mb=0.572,
            cumulative_bytes_sent=5_000_000,
            cumulative_bytes_recv=10_000_000,
            cumulative_packets_sent=2500,
            cumulative_packets_recv=5000,
            cumulative_transferred_mb=14.3,
            is_initial_sample=False,
        )

        with client.websocket_connect("/ws/metrics") as websocket:
            data_text = websocket.receive_text()
            data = json.loads(data_text)
            assert data["type"] == "initial_state"
            assert "data" in data
            metric_data = data["data"]
            assert metric_data["interface"] == "eth0"
            assert metric_data["upload_mbps"] == 4.5
            assert metric_data["download_mbps"] == 9.0
            assert metric_data["packets_sent_per_sec"] == 60.0
            assert metric_data["packets_received_per_sec"] == 120.0
            assert metric_data["session_transferred_mb"] == 0.572
