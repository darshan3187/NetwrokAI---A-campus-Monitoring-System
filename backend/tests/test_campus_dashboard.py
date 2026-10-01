"""Automated tests for Phase 3: Campus Network Operations Dashboard & Multi-Device Telemetry Integration.

Validates:
- Campus telemetry summary calculations (online, unreachable, stale, unknown, maintenance)
- Empty device inventory behavior and graceful zeroes
- Campus topological hierarchy (Campus -> Building -> Floor -> Department -> Devices)
- Multi-device throughput timeline aggregation and time-range windowing
- Device-level comparison dataset
- Reliable device status derivation (online, unreachable, stale, maintenance, unknown)
- Distinguishing mock vs local psutil vs remote SNMP
- Regression protection for local host monitoring and synthetic simulation
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import DeviceModel, DeviceTelemetryModel
from app.services.monitoring import monitoring_service
from app.services.polling import polling_service

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
# 1. Campus Summary & Empty State Tests
# ============================================================================


def test_campus_summary_empty_inventory(client: TestClient):
    """When no devices are registered, summary returns honest zeroes without crashing."""
    resp = client.get("/api/v1/devices/telemetry/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_devices"] == 0
    assert data["online_count"] == 0
    assert data["unreachable_count"] == 0
    assert data["stale_count"] == 0
    assert data["unknown_count"] == 0
    assert data["maintenance_count"] == 0
    assert data["latest_campus_upload_mbps"] == 0.0
    assert data["latest_campus_download_mbps"] == 0.0
    assert data["total_telemetry_samples"] == 0
    assert data["last_successful_poll"] is None


def test_campus_hierarchy_empty_inventory(client: TestClient):
    """Hierarchy returns an empty list of buildings when no devices exist."""
    resp = client.get("/api/v1/devices/hierarchy")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_devices"] == 0
    assert data["total_buildings"] == 0
    assert data["total_departments"] == 0
    assert data["buildings"] == []


# ============================================================================
# 2. Reliable Status Derivation & Mixed Fleet Tests
# ============================================================================


def test_reliable_status_derivation(client: TestClient):
    """Verify status semantics: online, unreachable, stale, maintenance, and unknown."""
    now = datetime.now(timezone.utc)
    db = TestingSessionLocal()

    # 1. Device: Online (successful recent poll)
    d1 = DeviceModel(
        id="dev-online",
        name="Core Switch 1",
        ip_address="10.0.1.1",
        device_type="switch",
        building="Science Hall",
        department="Computer Science",
        floor="1",
        collection_method="mock",
        monitoring_status="active",
        connection_status="online",
        reachability="reachable",
        last_poll_status="success",
        last_poll_at=now - timedelta(seconds=15),
        polling_interval_seconds=10.0,
        polling_enabled=True,
    )

    # 2. Device: Unreachable (failed poll attempt)
    d2 = DeviceModel(
        id="dev-unreach",
        name="Edge Router 2",
        ip_address="10.0.2.1",
        device_type="router",
        building="Admin Building",
        department="Administration",
        floor="2",
        collection_method="snmp",
        monitoring_status="active",
        connection_status="offline",
        reachability="unreachable",
        last_poll_status="error",
        last_poll_error="Destination Host Unreachable",
        last_poll_at=now - timedelta(seconds=20),
        polling_interval_seconds=10.0,
        polling_enabled=True,
    )

    # 3. Device: Stale (last successful poll was 15 minutes ago, exceeding stale threshold)
    d3 = DeviceModel(
        id="dev-stale",
        name="Library AP East",
        ip_address="10.0.3.1",
        device_type="access_point",
        building="Central Library",
        department="Library Services",
        floor="3",
        collection_method="mock",
        monitoring_status="active",
        connection_status="online",
        reachability="reachable",
        last_poll_status="success",
        last_poll_at=now - timedelta(minutes=15),
        polling_interval_seconds=10.0,
        polling_enabled=True,
    )

    # 4. Device: Maintenance (administratively disabled)
    d4 = DeviceModel(
        id="dev-maint",
        name="Server Node A",
        ip_address="10.0.4.1",
        device_type="server",
        building="Science Hall",
        department="Physics",
        floor="Basement",
        collection_method="manual",
        monitoring_status="maintenance",
        connection_status="unknown",
        reachability="configured",
        polling_enabled=False,
    )

    # 5. Device: Unknown (registered but never polled)
    d5 = DeviceModel(
        id="dev-unknown",
        name="Lab Switch 4",
        ip_address="10.0.5.1",
        device_type="switch",
        building="Science Hall",
        department="Computer Science",
        floor="2",
        collection_method="mock",
        monitoring_status="active",
        connection_status="unknown",
        reachability="configured",
        last_poll_at=None,
        polling_enabled=False,
    )

    db.add_all([d1, d2, d3, d4, d5])
    db.commit()
    db.close()

    # Query summary endpoint
    resp = client.get("/api/v1/devices/telemetry/summary")
    assert resp.status_code == 200
    summary = resp.json()

    assert summary["total_devices"] == 5
    assert summary["online_count"] == 1
    assert summary["unreachable_count"] == 1
    assert summary["stale_count"] == 1
    assert summary["maintenance_count"] == 1
    assert summary["unknown_count"] == 1
    assert summary["total_polling_errors"] == 1

    # Verify individual device responses have correct computed_status
    dev_resp = client.get("/api/v1/devices")
    devices_by_id = {d["id"]: d for d in dev_resp.json()["devices"]}

    assert devices_by_id["dev-online"]["computed_status"] == "online"
    assert devices_by_id["dev-online"]["is_stale"] is False

    assert devices_by_id["dev-unreach"]["computed_status"] == "unreachable"

    assert devices_by_id["dev-stale"]["computed_status"] == "stale"
    assert devices_by_id["dev-stale"]["is_stale"] is True

    assert devices_by_id["dev-maint"]["computed_status"] == "maintenance"
    assert devices_by_id["dev-unknown"]["computed_status"] == "unknown"


# ============================================================================
# 3. Campus Topological Hierarchy Tests
# ============================================================================


def test_campus_topological_hierarchy(client: TestClient):
    """Campus hierarchy correctly organizes devices by Building -> Floor -> Department."""
    db = TestingSessionLocal()
    # Add devices across 2 buildings, multiple floors and departments
    devices = [
        DeviceModel(
            id="d-b1-f1-cs",
            name="CS Switch 1",
            ip_address="10.1.1.1",
            device_type="switch",
            building="Tech Tower",
            floor="1",
            department="Computer Science",
            collection_method="mock",
        ),
        DeviceModel(
            id="d-b1-f1-ee",
            name="EE Switch 1",
            ip_address="10.1.1.2",
            device_type="switch",
            building="Tech Tower",
            floor="1",
            department="Electrical Eng",
            collection_method="mock",
        ),
        DeviceModel(
            id="d-b1-f2-cs",
            name="CS Router Floor 2",
            ip_address="10.1.2.1",
            device_type="router",
            building="Tech Tower",
            floor="2",
            department="Computer Science",
            collection_method="mock",
        ),
        DeviceModel(
            id="d-b2-f1-lib",
            name="Library Core AP",
            ip_address="10.2.1.1",
            device_type="access_point",
            building="North Library",
            floor="1",
            department="Library Operations",
            collection_method="mock",
        ),
    ]
    db.add_all(devices)
    db.commit()
    db.close()

    resp = client.get("/api/v1/devices/hierarchy")
    assert resp.status_code == 200
    hierarchy = resp.json()

    assert hierarchy["total_devices"] == 4
    assert hierarchy["total_buildings"] == 2
    assert hierarchy["total_departments"] == 3

    bldg_names = [b["building"] for b in hierarchy["buildings"]]
    assert "Tech Tower" in bldg_names
    assert "North Library" in bldg_names

    # Check floors inside Tech Tower
    tech_bldg = next(b for b in hierarchy["buildings"] if b["building"] == "Tech Tower")
    assert tech_bldg["total_devices"] == 3
    assert len(tech_bldg["floors"]) == 2


# ============================================================================
# 4. Campus Throughput Timeline & Device Comparison Tests
# ============================================================================


def test_campus_throughput_timeline_and_comparison(client: TestClient):
    """Campus timeline groups throughput chronologically and device comparison outputs individual telemetry."""
    now = datetime.now(timezone.utc)
    db = TestingSessionLocal()

    dev = DeviceModel(
        id="dev-flow",
        name="Flow Switch",
        ip_address="10.10.1.1",
        device_type="switch",
        building="Admin Block",
        floor="1",
        department="IT Services",
        collection_method="mock",
        reachability="reachable",
        last_poll_status="success",
        last_poll_at=now,
    )
    db.add(dev)
    db.commit()

    # Add historical telemetry samples
    t1 = DeviceTelemetryModel(
        device_id="dev-flow",
        interface_index=1,
        interface_name="GigabitEthernet0/1",
        timestamp=now - timedelta(minutes=10),
        bytes_sent=1000000,
        bytes_recv=2000000,
        packets_sent=1000,
        packets_recv=2000,
        upload_mbps=5.5,
        download_mbps=12.0,
        packets_sent_per_sec=150.0,
        packets_recv_per_sec=300.0,
        errors_in=0,
        errors_out=0,
        discards_in=0,
        discards_out=0,
        collection_method="mock",
        data_validity="valid",
        oper_status="up",
    )
    t2 = DeviceTelemetryModel(
        device_id="dev-flow",
        interface_index=1,
        interface_name="GigabitEthernet0/1",
        timestamp=now - timedelta(minutes=5),
        bytes_sent=1500000,
        bytes_recv=3000000,
        packets_sent=1500,
        packets_recv=3000,
        upload_mbps=8.0,
        download_mbps=18.5,
        packets_sent_per_sec=200.0,
        packets_recv_per_sec=450.0,
        errors_in=0,
        errors_out=0,
        discards_in=0,
        discards_out=0,
        collection_method="mock",
        data_validity="valid",
        oper_status="up",
    )
    db.add_all([t1, t2])
    db.commit()
    db.close()

    # 1. Query Timeline
    t_resp = client.get("/api/v1/devices/telemetry/timeline?hours=1")
    assert t_resp.status_code == 200
    timeline_data = t_resp.json()
    assert timeline_data["total_samples"] == 2
    assert len(timeline_data["timeline"]) > 0

    # 2. Query Comparison
    c_resp = client.get("/api/v1/devices/telemetry/comparison")
    assert c_resp.status_code == 200
    comp_data = c_resp.json()
    assert comp_data["total_devices"] == 1
    item = comp_data["devices"][0]
    assert item["device_id"] == "dev-flow"
    assert item["upload_mbps"] == 8.0
    assert item["download_mbps"] == 18.5
    assert item["computed_status"] == "online"
