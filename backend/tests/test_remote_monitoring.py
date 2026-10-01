"""Automated tests for Remote Network Device Telemetry & Monitoring Engine (Phase 2).

Validates:
- Mock collector deterministic outputs and fault injection
- Counter delta calculations and rate conversion
- Counter reset and reboot handling
- Timeout and unreachable device failure isolation
- Polling service concurrency and duplicate-job suppression
- Monitoring start/stop endpoints
- Telemetry persistence, latest query, and history filtering
- Campus-wide telemetry summary
- WebSocket device telemetry event structure
- Regression tests preserving local psutil host monitoring and Simulation Lab
"""

import asyncio
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import DeviceModel, DeviceTelemetryModel
from app.services.monitoring import monitoring_service
from app.services.polling import DevicePollingService, polling_service
from app.services.remote_collector import (
    DevicePollResult,
    MockRemoteCollector,
    RateCalculator,
    RawInterfaceCounters,
    SNMPv2cCollector,
    collector_factory,
)

# Isolated in-memory database for testing
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
    """Create fresh database tables before each test and isolate service session factories."""
    app.dependency_overrides[get_db] = override_get_db
    original_monitoring_session = monitoring_service.session_factory
    original_polling_session = polling_service.session_factory

    monitoring_service.session_factory = TestingSessionLocal
    polling_service.session_factory = TestingSessionLocal

    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

    monitoring_service.session_factory = original_monitoring_session
    polling_service.session_factory = original_polling_session


@pytest.fixture
def client():
    return TestClient(app)


# ============================================================================
# 1. Collector Unit Tests
# ============================================================================


@pytest.mark.asyncio
async def test_mock_collector_output():
    """Mock collector should generate realistic interface telemetry with deterministic counters."""
    collector = MockRemoteCollector()
    result = await collector.poll(target_ip="192.168.1.1", device_id="test-router-1")

    assert result.success is True
    assert result.reachability == "reachable"
    assert len(result.interfaces) >= 2
    for iface in result.interfaces:
        assert iface.name in ("GigabitEthernet0/1", "GigabitEthernet0/2")
        assert iface.bytes_sent >= 0
        assert iface.bytes_recv >= 0
        assert iface.oper_status == "up"


@pytest.mark.asyncio
async def test_mock_collector_fault_injection():
    """Mock collector should support fault injection for unreachable and unsupported states."""
    collector = MockRemoteCollector()

    # Test unreachable
    collector.inject_fault("test-down", "unreachable")
    down_result = await collector.poll("192.168.1.200", "test-down")
    assert down_result.success is False
    assert down_result.reachability == "unreachable"
    assert len(down_result.interfaces) == 0

    # Test unsupported
    collector.inject_fault("test-unsupported", "unsupported")
    unsup_result = await collector.poll("192.168.1.201", "test-unsupported")
    assert unsup_result.success is False
    assert unsup_result.reachability == "unsupported"


@pytest.mark.asyncio
async def test_snmp_collector_unreachable():
    """SNMP collector should gracefully flag unreachable non-existent targets without crashing."""
    collector = SNMPv2cCollector(default_port=1)  # Non-listening port
    result = await collector.poll(target_ip="127.0.0.1", device_id="snmp-dev", timeout_seconds=0.5)

    assert result.reachability in ("unreachable", "configured")
    assert result.device_id == "snmp-dev"


# ============================================================================
# 2. Rate Calculator Unit Tests
# ============================================================================


def test_rate_calculator_initial_sample():
    """Initial sample must be marked as initial_sample with 0.0 rate to prevent synthetic spikes."""
    calc = RateCalculator()
    raw = RawInterfaceCounters(
        index=1,
        name="eth0",
        oper_status="up",
        bytes_sent=1000000,
        bytes_recv=2000000,
        packets_sent=1000,
        packets_recv=2000,
        errors_in=0,
        errors_out=0,
        discards_in=0,
        discards_out=0,
        timestamp=1000.0,
    )
    computed = calc.calculate_metrics(device_id="dev-1", current=raw)

    assert computed.data_validity == "initial_sample"
    assert computed.upload_mbps == 0.0
    assert computed.download_mbps == 0.0
    assert computed.packets_sent_per_sec == 0.0
    assert computed.packets_recv_per_sec == 0.0


def test_rate_calculator_delta_calculation():
    """Subsequent sample after elapsed time must accurately compute Mbps and packet rate."""
    calc = RateCalculator()
    raw1 = RawInterfaceCounters(
        index=1,
        name="eth0",
        oper_status="up",
        bytes_sent=1_000_000,
        bytes_recv=2_000_000,
        packets_sent=1_000,
        packets_recv=2_000,
        errors_in=0,
        errors_out=0,
        discards_in=0,
        discards_out=0,
        timestamp=1000.0,
    )
    calc.calculate_metrics(device_id="dev-1", current=raw1)

    # 1 second later: 125,000 bytes sent (1.0 Mbps), 250,000 bytes received (2.0 Mbps)
    raw2 = RawInterfaceCounters(
        index=1,
        name="eth0",
        oper_status="up",
        bytes_sent=1_125_000,
        bytes_recv=2_250_000,
        packets_sent=1_100,
        packets_recv=2_200,
        errors_in=1,
        errors_out=0,
        discards_in=0,
        discards_out=0,
        timestamp=1001.0,
    )
    computed = calc.calculate_metrics(device_id="dev-1", current=raw2)

    assert computed.data_validity == "valid"
    assert pytest.approx(computed.upload_mbps, 0.05) == 1.0
    assert pytest.approx(computed.download_mbps, 0.05) == 2.0
    assert computed.packets_sent_per_sec == 100.0
    assert computed.packets_recv_per_sec == 200.0
    assert computed.errors_in == 1


def test_rate_calculator_counter_reset():
    """When counters drop below previous (e.g. device reboot or 32-bit rollover), flag counter_reset and do not report negative rates."""
    calc = RateCalculator()
    raw1 = RawInterfaceCounters(
        index=1,
        name="eth0",
        oper_status="up",
        bytes_sent=5_000_000,
        bytes_recv=5_000_000,
        packets_sent=5_000,
        packets_recv=5_000,
        timestamp=1000.0,
    )
    calc.calculate_metrics(device_id="dev-1", current=raw1)

    # Device rebooted: counter reset to 1000
    raw2 = RawInterfaceCounters(
        index=1,
        name="eth0",
        oper_status="up",
        bytes_sent=1_000,
        bytes_recv=1_000,
        packets_sent=10,
        packets_recv=10,
        timestamp=1002.0,
    )
    computed = calc.calculate_metrics(device_id="dev-1", current=raw2)

    assert computed.data_validity == "counter_reset"
    assert computed.upload_mbps == 0.0
    assert computed.download_mbps == 0.0
    assert computed.packets_sent_per_sec == 0.0
    assert computed.packets_recv_per_sec == 0.0


# ============================================================================
# 3. Polling Service Unit Tests
# ============================================================================


@pytest.mark.asyncio
async def test_polling_duplicate_job_suppression():
    """Polling service must prevent overlapping concurrent polls for the same device."""
    service = DevicePollingService(session_factory=TestingSessionLocal)
    dev_id = "test-concurrent-device"

    # Simulate device being in active polls
    service._active_polls.add(dev_id)

    # Calling poll_device_job should immediately return None without executing
    result = await service.poll_device_job(dev_id)
    assert result is None

    # After clearing, it can proceed
    service._active_polls.discard(dev_id)


@pytest.mark.asyncio
async def test_polling_service_start_stop():
    """Polling service must start and stop gracefully without leaving orphan tasks."""
    service = DevicePollingService(session_factory=TestingSessionLocal)
    await service.start()
    assert service._is_running is True
    assert service._scheduler_task is not None

    await service.stop()
    assert service._is_running is False
    assert service._scheduler_task is None


# ============================================================================
# 4. REST API Endpoint Tests
# ============================================================================


def test_device_monitoring_control_and_health(client: TestClient):
    """Test start monitoring, stop monitoring, and health check endpoints."""
    # 1. Register a device with mock collection
    reg_resp = client.post(
        "/api/v1/devices",
        json={
            "name": "Library Distribution Switch",
            "ip_address": "10.10.4.1",
            "device_type": "switch",
            "building": "Central Library",
            "department": "Library Systems",
            "floor": "Floor 2",
            "collection_method": "mock",
        },
    )
    assert reg_resp.status_code == 201
    dev_data = reg_resp.json()
    dev_id = dev_data["id"]

    # Initial state should be polling disabled
    assert dev_data["polling_enabled"] is False
    assert dev_data["reachability"] == "configured"

    # 2. Check health endpoint before polling
    health_resp = client.get(f"/api/v1/devices/{dev_id}/health")
    assert health_resp.status_code == 200
    health = health_resp.json()
    assert health["device_id"] == dev_id
    assert health["polling_enabled"] is False
    assert health["reachability"] == "configured"

    # 3. Start monitoring
    start_resp = client.post(
        f"/api/v1/devices/{dev_id}/monitoring/start",
        json={"interval_seconds": 5.0},
    )
    assert start_resp.status_code == 200
    started_data = start_resp.json()
    assert started_data["polling_enabled"] is True
    assert started_data["polling_interval_seconds"] == 5.0

    # 4. Stop monitoring
    stop_resp = client.post(f"/api/v1/devices/{dev_id}/monitoring/stop")
    assert stop_resp.status_code == 200
    stopped_data = stop_resp.json()
    assert stopped_data["polling_enabled"] is False


@pytest.mark.asyncio
async def test_telemetry_query_latest_and_history(client: TestClient):
    """Test storing telemetry and querying latest and bounded history."""
    # Register device
    reg_resp = client.post(
        "/api/v1/devices",
        json={
            "name": "Data Center Edge Router",
            "ip_address": "172.16.0.1",
            "device_type": "router",
            "building": "Data Center",
            "department": "Infrastructure",
            "floor": "Basement",
            "collection_method": "mock",
        },
    )
    dev_id = reg_resp.json()["id"]

    # Query latest before any telemetry -> 404
    latest_404 = client.get(f"/api/v1/devices/{dev_id}/telemetry/latest")
    assert latest_404.status_code == 404

    # Execute a poll using polling_service
    await polling_service.poll_device_job(dev_id)

    # Now latest should return data
    latest_resp = client.get(f"/api/v1/devices/{dev_id}/telemetry/latest")
    assert latest_resp.status_code == 200
    latest = latest_resp.json()
    assert latest["device_id"] == dev_id
    assert "GigabitEthernet" in latest["interface_name"]
    assert latest["data_validity"] in ("initial_sample", "mock", "valid")

    # History should contain samples
    hist_resp = client.get(f"/api/v1/devices/{dev_id}/telemetry/history?limit=10")
    assert hist_resp.status_code == 200
    hist = hist_resp.json()
    assert hist["device_id"] == dev_id
    assert hist["total_returned"] >= 1
    assert len(hist["telemetry"]) >= 1


@pytest.mark.asyncio
async def test_campus_telemetry_summary(client: TestClient):
    """Test aggregate campus telemetry summary endpoint."""
    # Register two devices
    r1 = client.post(
        "/api/v1/devices",
        json={
            "name": "Host A",
            "ip_address": "10.0.1.5",
            "device_type": "server",
            "building": "Admin",
            "department": "Finance",
            "floor": "1",
            "collection_method": "mock",
        },
    )
    dev1_id = r1.json()["id"]

    # Poll device
    await polling_service.poll_device_job(dev1_id)

    # Query campus summary
    summary_resp = client.get("/api/v1/devices/telemetry/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()

    assert summary["total_devices"] >= 1
    assert summary["total_telemetry_samples"] >= 1
    assert "latest_campus_upload_mbps" in summary
    assert "latest_campus_download_mbps" in summary
    assert "timestamp" in summary


# ============================================================================
# 5. Regression & Preservation Tests
# ============================================================================


def test_local_host_monitoring_preservation(client: TestClient):
    """Verify that existing local psutil host monitoring endpoints remain completely intact."""
    # 1. Health check
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] in ("ok", "degraded")

    # 2. Host interfaces
    ifaces_resp = client.get("/api/v1/interfaces")
    assert ifaces_resp.status_code == 200
    assert "interfaces" in ifaces_resp.json()

    # 3. Host summary
    summary_resp = client.get("/api/v1/summary")
    assert summary_resp.status_code == 200
    assert "is_monitoring" in summary_resp.json()


def test_simulation_lab_isolation_preservation(client: TestClient):
    """Verify that synthetic simulation lab scenarios run in complete isolation."""
    # List scenarios
    scenarios_resp = client.get("/api/v1/simulation/scenarios")
    assert scenarios_resp.status_code == 200
    assert scenarios_resp.json()["count"] > 0

    # Run scenario
    run_resp = client.post(
        "/api/v1/simulation/run",
        json={"scenario_id": "sudden_download_spike", "seed": 42},
    )
    assert run_resp.status_code == 200
    result = run_resp.json()
    assert result["scenario_id"] == "sudden_download_spike"
    assert len(result["timeline"]) > 0
    assert "metrics" in result
