"""Automated tests for Campus Multi-Device Registry (Phase 1).

Validates device registration, IP validation, required field enforcement,
query filters, partial updates, deletions, inventory summaries, and ensures
that existing local host monitoring and synthetic simulation remain intact.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import DeviceModel
from app.services.monitoring import monitoring_service

# Isolated in-memory SQLite database for deterministic testing
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
    """Create fresh database tables before each test and drop them afterwards."""
    app.dependency_overrides[get_db] = override_get_db
    original_session_factory = monitoring_service.session_factory
    monitoring_service.session_factory = TestingSessionLocal
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    monitoring_service.session_factory = original_session_factory


@pytest.fixture
def client():
    return TestClient(app)


def test_create_device_success_ipv4(client: TestClient):
    """Test successful device registration with a valid IPv4 address and auto-generated ID."""
    payload = {
        "name": "Core Router East",
        "ip_address": "10.0.1.1",
        "device_type": "router",
        "building": "Engineering Hall",
        "department": "Computer Science",
        "floor": "3",
        "location_description": "Rack A-01, Server Room 302",
        "vendor_model": "Cisco Catalyst 8300",
        "collection_method": "manual",
        "monitoring_status": "active",
        "connection_status": "unknown",
    }
    response = client.post("/api/v1/devices", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Core Router East"
    assert data["ip_address"] == "10.0.1.1"
    assert data["device_type"] == "router"
    assert data["building"] == "Engineering Hall"
    assert data["department"] == "Computer Science"
    assert data["floor"] == "3"
    assert data["vendor_model"] == "Cisco Catalyst 8300"
    assert data["id"].startswith("dev-")
    assert "created_at" in data
    assert "updated_at" in data


def test_create_device_success_ipv6_and_custom_id(client: TestClient):
    """Test successful device registration with IPv6 and custom device ID."""
    payload = {
        "id": "switch-cs-lab-01",
        "name": "Lab Access Switch 1",
        "ip_address": "2001:db8:85a3::8a2e:370:7334",
        "device_type": "switch",
        "building": "Science Complex",
        "department": "IT Infrastructure",
        "floor": "Ground",
        "collection_method": "snmp",
        "monitoring_status": "active",
        "connection_status": "unknown",
    }
    response = client.post("/api/v1/devices", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "switch-cs-lab-01"
    assert data["ip_address"] == "2001:db8:85a3::8a2e:370:7334"
    assert data["device_type"] == "switch"
    assert data["floor"] == "Ground"


def test_create_device_invalid_ip(client: TestClient):
    """Test that invalid IP address formats are rejected with 422 Unprocessable Entity."""
    invalid_ips = ["999.999.999.999", "192.168.1.500", "not-an-ip", "10.0.0.1.2"]
    for ip in invalid_ips:
        payload = {
            "name": "Invalid Device",
            "ip_address": ip,
            "device_type": "router",
            "building": "Main Block",
            "department": "CS",
            "floor": "1",
        }
        response = client.post("/api/v1/devices", json=payload)
        assert response.status_code == 422, f"Expected 422 for IP '{ip}', got {response.status_code}"


def test_create_device_missing_required_fields(client: TestClient):
    """Test validation errors when mandatory fields are omitted or empty."""
    # Missing name
    res1 = client.post(
        "/api/v1/devices",
        json={"ip_address": "10.0.0.2", "device_type": "switch", "building": "B1", "department": "EE", "floor": "2"},
    )
    assert res1.status_code == 422

    # Empty string building
    res2 = client.post(
        "/api/v1/devices",
        json={"name": "AP 1", "ip_address": "10.0.0.2", "device_type": "access_point", "building": "  ", "department": "EE", "floor": "2"},
    )
    assert res2.status_code == 422

    # Invalid device type
    res3 = client.post(
        "/api/v1/devices",
        json={"name": "Bad Type", "ip_address": "10.0.0.3", "device_type": "supercomputer", "building": "B1", "department": "CS", "floor": "1"},
    )
    assert res3.status_code == 422

    # Invalid collection method
    res4 = client.post(
        "/api/v1/devices",
        json={"name": "Bad Method", "ip_address": "10.0.0.4", "device_type": "switch", "building": "B1", "department": "CS", "floor": "1", "collection_method": "satellite"},
    )
    assert res4.status_code == 422


def test_create_device_duplicate_ip_conflict(client: TestClient):
    """Test that registering a duplicate IP address returns 409 Conflict."""
    payload = {
        "name": "Device 1",
        "ip_address": "192.168.10.1",
        "device_type": "router",
        "building": "Tower A",
        "department": "Network Ops",
        "floor": "4",
    }
    res1 = client.post("/api/v1/devices", json=payload)
    assert res1.status_code == 201

    # Attempt to register second device with same IP
    res2 = client.post(
        "/api/v1/devices",
        json={
            "name": "Device 2 Duplicate",
            "ip_address": "192.168.10.1",
            "device_type": "switch",
            "building": "Tower B",
            "department": "Civil",
            "floor": "1",
        },
    )
    assert res2.status_code == 409
    assert "already registered" in res2.json()["detail"]


def test_create_device_duplicate_id_conflict(client: TestClient):
    """Test that registering a duplicate device ID returns 409 Conflict."""
    payload = {
        "id": "fixed-id-01",
        "name": "AP Core",
        "ip_address": "192.168.1.10",
        "device_type": "access_point",
        "building": "Library",
        "department": "Library Services",
        "floor": "2",
    }
    res1 = client.post("/api/v1/devices", json=payload)
    assert res1.status_code == 201

    res2 = client.post(
        "/api/v1/devices",
        json={
            "id": "fixed-id-01",
            "name": "AP Core Second",
            "ip_address": "192.168.1.11",
            "device_type": "access_point",
            "building": "Library",
            "department": "Library Services",
            "floor": "3",
        },
    )
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_device_listing_and_filtering(client: TestClient):
    """Test listing devices with device_type, department, building, and search filters."""
    # Seed 3 devices
    dev1 = {
        "id": "dev-cs-rtr",
        "name": "CS Department Gateway",
        "ip_address": "10.10.1.1",
        "device_type": "router",
        "building": "Turing Block",
        "department": "Computer Science",
        "floor": "1",
        "monitoring_status": "active",
        "connection_status": "online",
    }
    dev2 = {
        "id": "dev-ee-sw",
        "name": "EE Lab Distribution Switch",
        "ip_address": "10.20.1.1",
        "device_type": "switch",
        "building": "Maxwell Hall",
        "department": "Electrical Eng",
        "floor": "2",
        "monitoring_status": "active",
        "connection_status": "unknown",
    }
    dev3 = {
        "id": "dev-lib-ap",
        "name": "Library Main AP",
        "ip_address": "10.30.1.1",
        "device_type": "access_point",
        "building": "Library Center",
        "department": "Library Services",
        "floor": "Ground",
        "monitoring_status": "maintenance",
        "connection_status": "offline",
    }
    for d in [dev1, dev2, dev3]:
        r = client.post("/api/v1/devices", json=d)
        assert r.status_code == 201

    # List all
    all_res = client.get("/api/v1/devices")
    assert all_res.status_code == 200
    assert all_res.json()["total"] == 3

    # Filter by device_type
    rtr_res = client.get("/api/v1/devices?device_type=router")
    assert rtr_res.status_code == 200
    assert rtr_res.json()["total"] == 1
    assert rtr_res.json()["devices"][0]["name"] == "CS Department Gateway"

    # Filter by department
    ee_res = client.get("/api/v1/devices?department=Electrical Eng")
    assert ee_res.status_code == 200
    assert ee_res.json()["total"] == 1
    assert ee_res.json()["devices"][0]["id"] == "dev-ee-sw"

    # Filter by building
    bldg_res = client.get("/api/v1/devices?building=Library Center")
    assert bldg_res.status_code == 200
    assert bldg_res.json()["total"] == 1
    assert bldg_res.json()["devices"][0]["device_type"] == "access_point"

    # Filter by monitoring status
    maint_res = client.get("/api/v1/devices?monitoring_status=maintenance")
    assert maint_res.status_code == 200
    assert maint_res.json()["total"] == 1

    # Search filter
    search_res = client.get("/api/v1/devices?search=Turing")
    assert search_res.status_code == 200
    assert search_res.json()["total"] == 1
    assert search_res.json()["devices"][0]["building"] == "Turing Block"

    search_ip = client.get("/api/v1/devices?search=10.20")
    assert search_ip.status_code == 200
    assert search_ip.json()["total"] == 1


def test_device_summary_endpoint(client: TestClient):
    """Test device summary endpoint aggregations."""
    # When empty
    empty_res = client.get("/api/v1/devices/summary")
    assert empty_res.status_code == 200
    summary = empty_res.json()
    assert summary["total_devices"] == 0
    assert summary["online_count"] == 0
    assert summary["active_count"] == 0

    # Add devices
    client.post(
        "/api/v1/devices",
        json={
            "name": "Router 1",
            "ip_address": "192.168.1.1",
            "device_type": "router",
            "building": "Hall A",
            "department": "CS",
            "floor": "1",
            "monitoring_status": "active",
            "connection_status": "online",
            "collection_method": "manual",
        },
    )
    client.post(
        "/api/v1/devices",
        json={
            "name": "Switch 1",
            "ip_address": "192.168.1.2",
            "device_type": "switch",
            "building": "Hall A",
            "department": "CS",
            "floor": "2",
            "monitoring_status": "active",
            "connection_status": "unknown",
            "collection_method": "snmp",
        },
    )
    client.post(
        "/api/v1/devices",
        json={
            "name": "AP 1",
            "ip_address": "192.168.2.1",
            "device_type": "access_point",
            "building": "Hall B",
            "department": "Mechanical",
            "floor": "Ground",
            "monitoring_status": "maintenance",
            "connection_status": "offline",
            "collection_method": "manual",
        },
    )

    res = client.get("/api/v1/devices/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["total_devices"] == 3
    assert data["online_count"] == 1
    assert data["offline_count"] == 1
    assert data["unknown_count"] == 1
    assert data["active_count"] == 2
    assert data["maintenance_count"] == 1
    assert data["by_type"]["router"] == 1
    assert data["by_type"]["switch"] == 1
    assert data["by_type"]["access_point"] == 1
    assert data["by_department"]["CS"] == 2
    assert data["by_department"]["Mechanical"] == 1


def test_get_device_by_id(client: TestClient):
    """Test retrieving device details by device_id."""
    create_res = client.post(
        "/api/v1/devices",
        json={
            "id": "dev-target-01",
            "name": "Target Switch",
            "ip_address": "172.16.0.1",
            "device_type": "switch",
            "building": "Data Center",
            "department": "Central IT",
            "floor": "Basement",
        },
    )
    assert create_res.status_code == 201

    get_res = client.get("/api/v1/devices/dev-target-01")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Target Switch"

    not_found = client.get("/api/v1/devices/non-existent-device")
    assert not_found.status_code == 404


def test_update_device(client: TestClient):
    """Test partial updates to device metadata and IP address."""
    create_res = client.post(
        "/api/v1/devices",
        json={
            "id": "dev-update-test",
            "name": "Original Name",
            "ip_address": "172.16.10.1",
            "device_type": "server",
            "building": "Old Building",
            "department": "Admin",
            "floor": "1",
            "monitoring_status": "active",
        },
    )
    assert create_res.status_code == 201

    # Update name, building, and monitoring_status
    patch_res = client.patch(
        "/api/v1/devices/dev-update-test",
        json={
            "name": "Updated Server Name",
            "building": "New Tech Tower",
            "monitoring_status": "maintenance",
        },
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["name"] == "Updated Server Name"
    assert updated["building"] == "New Tech Tower"
    assert updated["monitoring_status"] == "maintenance"
    # Unchanged fields remain
    assert updated["ip_address"] == "172.16.10.1"
    assert updated["department"] == "Admin"

    # Test update 404
    missing_patch = client.patch("/api/v1/devices/ghost-device", json={"name": "New Name"})
    assert missing_patch.status_code == 404


def test_update_device_ip_conflict(client: TestClient):
    """Test that updating an IP address to one already registered returns 409."""
    client.post(
        "/api/v1/devices",
        json={
            "id": "dev-a",
            "name": "Device A",
            "ip_address": "10.0.0.10",
            "device_type": "router",
            "building": "B1",
            "department": "CS",
            "floor": "1",
        },
    )
    client.post(
        "/api/v1/devices",
        json={
            "id": "dev-b",
            "name": "Device B",
            "ip_address": "10.0.0.20",
            "device_type": "router",
            "building": "B1",
            "department": "CS",
            "floor": "1",
        },
    )

    # Attempt to change Device B's IP to Device A's IP
    res = client.patch("/api/v1/devices/dev-b", json={"ip_address": "10.0.0.10"})
    assert res.status_code == 409
    assert "already registered" in res.json()["detail"]


def test_delete_device(client: TestClient):
    """Test device deletion and subsequent retrieval."""
    client.post(
        "/api/v1/devices",
        json={
            "id": "dev-to-delete",
            "name": "Temporary AP",
            "ip_address": "192.168.100.5",
            "device_type": "access_point",
            "building": "Outdoor",
            "department": "Facilities",
            "floor": "Ground",
        },
    )

    del_res = client.delete("/api/v1/devices/dev-to-delete")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

    # Confirm it's gone
    get_res = client.get("/api/v1/devices/dev-to-delete")
    assert get_res.status_code == 404

    # Deleting again returns 404
    del_again = client.delete("/api/v1/devices/dev-to-delete")
    assert del_again.status_code == 404


def test_local_telemetry_regression(client: TestClient):
    """Regression test ensuring existing local host monitoring endpoints remain functional."""
    # Health endpoint
    health_res = client.get("/api/v1/health")
    assert health_res.status_code == 200
    health_data = health_res.json()
    assert "status" in health_data
    assert "database" in health_data

    # Interfaces endpoint
    iface_res = client.get("/api/v1/interfaces")
    assert iface_res.status_code == 200
    assert "interfaces" in iface_res.json()

    # Metrics history endpoint
    hist_res = client.get("/api/v1/metrics/history?limit=10")
    assert hist_res.status_code == 200
    assert "metrics" in hist_res.json()

    # Session summary endpoint
    summary_res = client.get("/api/v1/summary")
    assert summary_res.status_code == 200
    assert "total_stored_samples" in summary_res.json()


def test_simulation_isolation_regression(client: TestClient):
    """Regression test verifying simulation lab remains strictly isolated from production DB."""
    # Scenarios list
    scenarios_res = client.get("/api/v1/simulation/scenarios")
    assert scenarios_res.status_code == 200
    scenarios = scenarios_res.json()["scenarios"]
    assert len(scenarios) > 0

    first_scenario = scenarios[0]["scenario_id"]

    # Run simulation
    run_res = client.post("/api/v1/simulation/run", json={"scenario_id": first_scenario, "seed": 42})
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert "synthetic simulation" in run_data["disclaimer"].lower()

    # Ensure no devices or production metrics were created by simulation
    dev_res = client.get("/api/v1/devices")
    assert dev_res.json()["total"] == 0
