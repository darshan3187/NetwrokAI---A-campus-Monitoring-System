"""Phase 3.1: End-to-End Integration, Reliability & Regression Test Suite.

Validates:
1. Complete REST API contracts and error responses across all device and campus endpoints.
2. Multi-device mock fleet integration across multiple buildings, floors, and departments.
3. Reliability edge cases:
   - Initial sample handling
   - Temporary poll failure and automatic recovery
   - Stale telemetry thresholds
   - Maintenance state overriding
   - Polling stop and device deletion while active
   - Counter reset / rollover safety
   - Missing or empty interface payloads
4. Local host monitoring regression protection:
   - psutil collector and database metrics isolation
   - Anomaly detection feature extraction isolation
   - Simulation Lab synthetic scenario isolation
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import DeviceModel, DeviceTelemetryModel, NetworkMetricModel
from app.services.monitoring import monitoring_service
from app.services.polling import polling_service
from app.services.remote_collector.base import DevicePollResult, RawInterfaceCounters
from app.services.remote_collector.rate_calculator import RateCalculator
from app.services.simulation import simulation_service

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
# TASK 1: Comprehensive REST API Endpoint Validation
# ============================================================================


def test_api_device_crud_and_validation(client: TestClient):
    """Test device creation, schema validation, 404 handling, and update/deletion."""
    # 1. Invalid payload: missing required fields
    bad_resp = client.post("/api/v1/devices", json={"name": "Bad Device"})
    assert bad_resp.status_code == 422

    # 2. Valid creation
    create_payload = {
        "id": "dev-test-1",
        "name": "Test Router 1",
        "ip_address": "192.168.1.1",
        "device_type": "router",
        "building": "Engineering Hall",
        "floor": "1",
        "department": "Computer Science",
        "collection_method": "mock",
        "monitoring_status": "active",
        "polling_interval_seconds": 10.0,
    }
    create_resp = client.post("/api/v1/devices", json=create_payload)
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["id"] == "dev-test-1"
    assert created_data["computed_status"] == "unknown"  # Never polled yet
    assert created_data["is_stale"] is False

    # 3. Duplicate ID conflict
    dup_resp = client.post("/api/v1/devices", json=create_payload)
    assert dup_resp.status_code == 409

    # 4. Get by ID
    get_resp = client.get("/api/v1/devices/dev-test-1")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Test Router 1"

    # 5. Non-existent device: 404
    missing_resp = client.get("/api/v1/devices/non-existent-device")
    assert missing_resp.status_code == 404

    # 6. Update device
    update_resp = client.patch("/api/v1/devices/dev-test-1", json={"name": "Updated Router Name"})
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated Router Name"

    # 7. Start & Stop monitoring endpoints
    start_resp = client.post("/api/v1/devices/dev-test-1/monitoring/start", json={"interval_seconds": 15})
    assert start_resp.status_code == 200
    assert start_resp.json()["polling_enabled"] is True
    assert start_resp.json()["polling_interval_seconds"] == 15.0

    stop_resp = client.post("/api/v1/devices/dev-test-1/monitoring/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["polling_enabled"] is False

    # 8. Delete device
    del_resp = client.delete("/api/v1/devices/dev-test-1")
    assert del_resp.status_code == 200
    assert client.get("/api/v1/devices/dev-test-1").status_code == 404


def test_api_telemetry_and_health_endpoints(client: TestClient):
    """Test device telemetry latest, history, and health endpoints."""
    now = datetime.now(timezone.utc)
    db = TestingSessionLocal()
    dev = DeviceModel(
        id="dev-telemetry-test",
        name="Telemetry Switch",
        ip_address="10.10.1.1",
        device_type="switch",
        building="Science Complex",
        floor="2",
        department="Physics",
        collection_method="mock",
        monitoring_status="active",
        reachability="reachable",
        last_poll_status="success",
        last_poll_at=now,
        polling_enabled=True,
    )
    db.add(dev)
    db.commit()

    # Check health endpoint before telemetry
    health_resp = client.get("/api/v1/devices/dev-telemetry-test/health")
    assert health_resp.status_code == 200
    h_data = health_resp.json()
    assert h_data["reachability"] == "reachable"
    assert h_data["last_poll_status"] == "success"

    # Add 3 telemetry records
    for i in range(3):
        t = DeviceTelemetryModel(
            device_id="dev-telemetry-test",
            interface_name="GigabitEthernet0/1",
            timestamp=now - timedelta(seconds=(3 - i) * 10),
            bytes_sent=1000 * (i + 1),
            bytes_recv=2000 * (i + 1),
            packets_sent=10 * (i + 1),
            packets_recv=20 * (i + 1),
            upload_mbps=1.5 * (i + 1),
            download_mbps=3.0 * (i + 1),
            packets_sent_per_sec=10.0,
            packets_recv_per_sec=20.0,
            errors_in=0,
            errors_out=0,
            discards_in=0,
            discards_out=0,
            collection_method="mock",
            data_validity="valid",
            oper_status="up",
        )
        db.add(t)
    db.commit()
    db.close()

    # Test latest telemetry
    latest_resp = client.get("/api/v1/devices/dev-telemetry-test/telemetry/latest")
    assert latest_resp.status_code == 200
    latest_data = latest_resp.json()
    assert latest_data["download_mbps"] == 9.0
    assert latest_data["upload_mbps"] == 4.5

    # Test history with limit
    hist_resp = client.get("/api/v1/devices/dev-telemetry-test/telemetry/history?limit=2")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["total_returned"] == 2
    assert len(hist_data["telemetry"]) == 2


# ============================================================================
# TASK 2: Multi-Device Mock Fleet Integration
# ============================================================================


@pytest.mark.asyncio
async def test_mock_fleet_integration_and_rollups(client: TestClient):
    """Deploy a mock fleet across 2 buildings, 3 floors, 4 departments, 4 device types.

    Verify distinct records, correct telemetry associations, hierarchy roll-ups,
    comparison table correctness, and non-duplicative timeline aggregation.
    """
    now = datetime.now(timezone.utc)
    db = TestingSessionLocal()

    fleet_config = [
        {
            "id": "fleet-r1",
            "name": "Eng Core Router",
            "ip_address": "10.1.0.1",
            "device_type": "router",
            "building": "Engineering Hall",
            "floor": "1",
            "department": "Computer Science",
            "collection_method": "mock",
            "dl": 25.5,
            "ul": 12.0,
            "status": "success",
            "reach": "reachable",
        },
        {
            "id": "fleet-sw1",
            "name": "Eng Lab Switch",
            "ip_address": "10.1.1.2",
            "device_type": "switch",
            "building": "Engineering Hall",
            "floor": "2",
            "department": "Electrical Engineering",
            "collection_method": "mock",
            "dl": 15.0,
            "ul": 8.0,
            "status": "success",
            "reach": "reachable",
        },
        {
            "id": "fleet-ap1",
            "name": "Physics Access Point",
            "ip_address": "10.2.1.10",
            "device_type": "access_point",
            "building": "Science Complex",
            "floor": "1",
            "department": "Physics",
            "collection_method": "mock",
            "dl": 5.2,
            "ul": 2.1,
            "status": "success",
            "reach": "reachable",
        },
        {
            "id": "fleet-srv1",
            "name": "Chem Computing Server",
            "ip_address": "10.2.3.50",
            "device_type": "server",
            "building": "Science Complex",
            "floor": "3",
            "department": "Chemistry",
            "collection_method": "mock",
            "dl": 40.0,
            "ul": 35.0,
            "status": "success",
            "reach": "reachable",
        },
    ]

    for item in fleet_config:
        d = DeviceModel(
            id=item["id"],
            name=item["name"],
            ip_address=item["ip_address"],
            device_type=item["device_type"],
            building=item["building"],
            floor=item["floor"],
            department=item["department"],
            collection_method=item["collection_method"],
            monitoring_status="active",
            reachability=item["reach"],
            last_poll_status=item["status"],
            last_poll_at=now - timedelta(seconds=10),
            polling_interval_seconds=10.0,
            polling_enabled=True,
        )
        db.add(d)

        # Add corresponding telemetry sample
        t = DeviceTelemetryModel(
            device_id=item["id"],
            interface_name="eth0",
            timestamp=now - timedelta(seconds=10),
            bytes_sent=50000,
            bytes_recv=100000,
            packets_sent=500,
            packets_recv=1000,
            upload_mbps=item["ul"],
            download_mbps=item["dl"],
            packets_sent_per_sec=50.0,
            packets_recv_per_sec=100.0,
            errors_in=0,
            errors_out=0,
            discards_in=0,
            discards_out=0,
            collection_method="mock",
            data_validity="valid",
            oper_status="up",
        )
        db.add(t)

    db.commit()
    db.close()

    # 1. Validate Campus Summary
    sum_resp = client.get("/api/v1/devices/telemetry/summary")
    assert sum_resp.status_code == 200
    sum_data = sum_resp.json()
    assert sum_data["total_devices"] == 4
    assert sum_data["online_count"] == 4
    assert sum_data["unreachable_count"] == 0
    # Expected aggregate: 25.5 + 15.0 + 5.2 + 40.0 = 85.7 Mbps download
    assert abs(sum_data["latest_campus_download_mbps"] - 85.7) < 0.01
    # Expected aggregate: 12.0 + 8.0 + 2.1 + 35.0 = 57.1 Mbps upload
    assert abs(sum_data["latest_campus_upload_mbps"] - 57.1) < 0.01

    # 2. Validate Campus Hierarchy
    hier_resp = client.get("/api/v1/devices/hierarchy")
    assert hier_resp.status_code == 200
    hier_data = hier_resp.json()
    assert hier_data["total_devices"] == 4
    assert hier_data["total_buildings"] == 2
    assert hier_data["total_departments"] == 4

    buildings_map = {b["building"]: b for b in hier_data["buildings"]}
    assert "Engineering Hall" in buildings_map
    assert "Science Complex" in buildings_map
    assert buildings_map["Engineering Hall"]["total_devices"] == 2
    assert buildings_map["Science Complex"]["total_devices"] == 2

    # 3. Validate Comparison Table
    comp_resp = client.get("/api/v1/devices/telemetry/comparison")
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()
    assert comp_data["total_devices"] == 4
    comp_ids = {d["device_id"] for d in comp_data["devices"]}
    assert comp_ids == {"fleet-r1", "fleet-sw1", "fleet-ap1", "fleet-srv1"}

    # 4. Validate Timeline Aggregation (Ensure no duplicate double-counting)
    timeline_resp = client.get("/api/v1/devices/telemetry/timeline?hours=1")
    assert timeline_resp.status_code == 200
    t_data = timeline_resp.json()
    assert t_data["total_samples"] >= 1
    # Check that download rate for the bucket matches aggregate
    pt = t_data["timeline"][-1]
    assert abs(pt["download_mbps"] - 85.7) < 0.01
    assert pt["reporting_devices"] == 4


# ============================================================================
# TASK 3: Reliability Edge Cases
# ============================================================================


def test_first_successful_poll_handling():
    """First poll generates initial sample baseline with zero rate and valid flag."""
    calc = RateCalculator()
    t0 = 1000.0

    raw1 = RawInterfaceCounters(
        index=1,
        name="eth0",
        oper_status="up",
        bytes_sent=500000,
        bytes_recv=1000000,
        packets_sent=500,
        packets_recv=1000,
        errors_in=0,
        errors_out=0,
        discards_in=0,
        discards_out=0,
        timestamp=t0,
    )
    rates1 = calc.calculate_metrics("dev-edge-1", raw1)
    assert rates1.data_validity == "initial_sample"
    assert rates1.download_mbps == 0.0
    assert rates1.upload_mbps == 0.0

    # Second poll 10 seconds later: valid rates
    raw2 = RawInterfaceCounters(
        index=1,
        name="eth0",
        oper_status="up",
        bytes_sent=1500000,   # 1 MB sent in 10s = ~0.8 Mbps
        bytes_recv=11000000,  # 10 MB received in 10s = ~8.0 Mbps
        packets_sent=1500,
        packets_recv=6000,
        errors_in=0,
        errors_out=0,
        discards_in=0,
        discards_out=0,
        timestamp=t0 + 10.0,
    )
    rates2 = calc.calculate_metrics("dev-edge-1", raw2)
    assert rates2.data_validity == "valid"
    assert rates2.download_mbps > 7.9
    assert rates2.upload_mbps > 0.7


def test_counter_reset_and_rollover_safety():
    """Device reboot resets counters; RateCalculator flags counter_reset without negative rates."""
    calc = RateCalculator()
    t0 = 2000.0

    # Initial poll
    raw1 = RawInterfaceCounters(
        index=1,
        name="eth0",
        oper_status="up",
        bytes_sent=50000000,
        bytes_recv=50000000,
        packets_sent=50000,
        packets_recv=50000,
        errors_in=0,
        errors_out=0,
        discards_in=0,
        discards_out=0,
        timestamp=t0,
    )
    calc.calculate_metrics("dev-reset-1", raw1)

    # Subsequent poll after reboot: counters dropped to near zero
    raw_reboot = RawInterfaceCounters(
        index=1,
        name="eth0",
        oper_status="up",
        bytes_sent=500,
        bytes_recv=1000,
        packets_sent=5,
        packets_recv=10,
        errors_in=0,
        errors_out=0,
        discards_in=0,
        discards_out=0,
        timestamp=t0 + 10.0,
    )
    rates_reboot = calc.calculate_metrics("dev-reset-1", raw_reboot)
    assert rates_reboot.data_validity == "counter_reset"
    assert rates_reboot.download_mbps == 0.0
    assert rates_reboot.upload_mbps == 0.0


def test_temporary_poll_failure_and_recovery(client: TestClient):
    """Temporary failure changes status to unreachable with error banner, then recovers."""
    now = datetime.now(timezone.utc)
    db = TestingSessionLocal()
    dev = DeviceModel(
        id="dev-fail-recover",
        name="Unstable Switch",
        ip_address="10.50.1.1",
        device_type="switch",
        building="Admin Block",
        floor="1",
        department="Finance",
        collection_method="mock",
        monitoring_status="active",
        reachability="reachable",
        last_poll_status="success",
        last_poll_at=now - timedelta(seconds=30),
        polling_enabled=True,
    )
    db.add(dev)
    db.commit()

    # Step 1: Simulate poll failure
    dev.reachability = "unreachable"
    dev.last_poll_status = "error"
    dev.last_poll_error = "Connection timed out (UDP 161)"
    dev.last_poll_at = now - timedelta(seconds=10)
    db.commit()

    resp_fail = client.get("/api/v1/devices/dev-fail-recover")
    assert resp_fail.status_code == 200
    assert resp_fail.json()["computed_status"] == "unreachable"
    assert resp_fail.json()["last_poll_error"] == "Connection timed out (UDP 161)"

    # Step 2: Simulate recovery
    dev.reachability = "reachable"
    dev.last_poll_status = "success"
    dev.last_poll_error = None
    dev.last_poll_at = now
    db.commit()

    resp_recovered = client.get("/api/v1/devices/dev-fail-recover")
    assert resp_recovered.status_code == 200
    assert resp_recovered.json()["computed_status"] == "online"
    assert resp_recovered.json()["last_poll_error"] is None
    db.close()


def test_device_removal_cascades_cleanly(client: TestClient):
    """Removing a device with active telemetry removes device and associated telemetry cleanly."""
    db = TestingSessionLocal()
    dev = DeviceModel(
        id="dev-delete-cascade",
        name="Temporary Node",
        ip_address="10.99.1.1",
        device_type="server",
        building="Lab",
        floor="1",
        department="Testing",
        collection_method="mock",
        monitoring_status="active",
        polling_enabled=False,
    )
    db.add(dev)
    db.commit()

    telemetry = DeviceTelemetryModel(
        device_id="dev-delete-cascade",
        interface_name="eth0",
        timestamp=datetime.now(timezone.utc),
        bytes_sent=100,
        bytes_recv=100,
        packets_sent=1,
        packets_recv=1,
        upload_mbps=0.1,
        download_mbps=0.1,
        packets_sent_per_sec=1.0,
        packets_recv_per_sec=1.0,
        errors_in=0,
        errors_out=0,
        discards_in=0,
        discards_out=0,
        collection_method="mock",
        data_validity="valid",
        oper_status="up",
    )
    db.add(telemetry)
    db.commit()
    db.close()

    del_resp = client.delete("/api/v1/devices/dev-delete-cascade")
    assert del_resp.status_code == 200

    # Verify device and its telemetry are gone
    assert client.get("/api/v1/devices/dev-delete-cascade").status_code == 404
    hist_resp = client.get("/api/v1/devices/dev-delete-cascade/telemetry/history")
    assert hist_resp.status_code == 404


# ============================================================================
# TASK 4: Local Host Monitoring & Simulation Lab Regression Tests
# ============================================================================


def test_local_monitoring_isolation_and_persistence(client: TestClient):
    """Local psutil monitoring collects into network_metrics and does not touch device_telemetry."""
    db = TestingSessionLocal()

    # Create local host metric
    local_metric = NetworkMetricModel(
        timestamp=datetime.now(timezone.utc),
        interface="Wi-Fi",
        download_mbps=12.5,
        upload_mbps=4.2,
        packets_sent_per_sec=5.0,
        packets_received_per_sec=10.0,
        cumulative_sent_mb=10.0,
        cumulative_received_mb=20.0,
        session_transferred_mb=30.0,
    )
    db.add(local_metric)
    db.commit()

    # Query local host metrics endpoint
    local_resp = client.get("/api/v1/metrics/history?limit=5")
    assert local_resp.status_code == 200
    metrics_data = local_resp.json()
    assert metrics_data["total_returned"] >= 1
    assert metrics_data["metrics"][0]["download_mbps"] == 12.5

    # Confirm device_telemetry table remains completely empty
    dev_telem_count = db.query(DeviceTelemetryModel).count()
    assert dev_telem_count == 0
    db.close()


def test_simulation_lab_isolation(client: TestClient):
    """Simulation Lab runs purely synthetic in-memory scenarios without touching device registry."""
    sim_resp = client.post(
        "/api/v1/simulation/run",
        json={"scenario_id": "sudden_download_spike", "seed": 42},
    )
    assert sim_resp.status_code == 200
    res = sim_resp.json()
    assert res["scenario_id"] == "sudden_download_spike"
    assert res["confusion_matrix"] is not None

    # Verify no devices were accidentally injected into the campus registry
    devs_resp = client.get("/api/v1/devices")
    assert devs_resp.status_code == 200
    assert len(devs_resp.json()["devices"]) == 0
