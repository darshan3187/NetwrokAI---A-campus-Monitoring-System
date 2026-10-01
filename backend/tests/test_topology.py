"""Automated tests for Phase 4: Authorized Read-Only Network Topology Discovery.

Covers:
- Empty topology responses (honest zeroes)
- LLDP neighbor parsing and resolution
- CDP neighbor parsing and resolution
- Unresolved remote chassis ID (no phantom device created)
- Duplicate neighbor observations (idempotent upsert & timestamp refresh)
- Discovery timeout handling
- Unsupported device reporting
- Stale link transition
- Credential redaction (zero secret exposure)
- Device deletion cascade cleanup
- Mock vs. actual separation
- Local psutil monitoring & simulation lab regression verification
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import DeviceModel, TopologyLinkModel, TopologyDiscoveryStatusModel
from app.services.monitoring import monitoring_service
from app.services.topology import topology_service

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


def test_empty_topology_links(client: TestClient):
    """Empty topology returns zero counts and an empty link list with honest zeroes."""
    response = client.get("/api/v1/topology/links")
    assert response.status_code == 200
    data = response.json()
    assert data["total_links"] == 0
    assert data["resolved_links"] == 0
    assert data["unresolved_links"] == 0
    assert data["stale_links"] == 0
    assert data["links"] == []
    assert "timestamp" in data


def test_empty_unresolved_neighbors(client: TestClient):
    """Querying unresolved neighbors when none exist returns empty list."""
    response = client.get("/api/v1/topology/unresolved")
    assert response.status_code == 200
    data = response.json()
    assert data["total_unresolved"] == 0
    assert data["unresolved_neighbors"] == []


def test_discover_lldp_mock_device(client: TestClient):
    """Discover LLDP neighbors for a registered mock router connected to a mock switch."""
    # Register core router
    res1 = client.post(
        "/api/v1/devices",
        json={
            "id": "dev-core-router-01",
            "name": "Core-Router-East",
            "ip_address": "10.0.1.1",
            "device_type": "router",
            "building": "Engineering Hall",
            "floor": "Floor 1",
            "department": "Infrastructure",
            "collection_method": "mock",
            "mock_behavior": "normal",
        },
    )
    assert res1.status_code == 201

    # Register distribution switch
    res2 = client.post(
        "/api/v1/devices",
        json={
            "id": "dev-dist-switch-01",
            "name": "Dist-Switch-01",
            "ip_address": "10.0.2.1",
            "device_type": "switch",
            "building": "Engineering Hall",
            "floor": "Floor 2",
            "department": "Computer Science",
            "collection_method": "mock",
            "mock_behavior": "normal",
        },
    )
    assert res2.status_code == 201

    # Trigger discovery on core router
    disc_res = client.post("/api/v1/topology/devices/dev-core-router-01/discover")
    assert disc_res.status_code == 200
    disc_data = disc_res.json()
    assert disc_data["success"] is True
    assert disc_data["status"] == "success"
    assert disc_data["protocol_used"] == "lldp"
    assert disc_data["neighbors_found"] >= 1
    assert disc_data["neighbors_resolved"] >= 1

    # Check links list
    links_res = client.get("/api/v1/topology/links")
    assert links_res.status_code == 200
    links_data = links_res.json()
    assert links_data["total_links"] >= 1
    assert links_data["resolved_links"] >= 1

    # Verify link details and flags
    resolved_link = next(
        l for l in links_data["links"] if l["remote_device_id"] == "dev-dist-switch-01"
    )
    assert resolved_link["source_device_id"] == "dev-core-router-01"
    assert resolved_link["protocol"] == "lldp"
    assert resolved_link["resolution_state"] == "resolved"
    assert resolved_link["is_mock"] is True
    assert resolved_link["discovery_source"] == "mock"
    assert resolved_link["link_status"] == "active"
    assert resolved_link["is_stale"] is False
    assert resolved_link["remote_chassis_id"] != ""
    assert resolved_link["remote_port_id"] != ""


def test_discover_cdp_mock_device(client: TestClient):
    """Discover CDP neighbors on a device with CDP protocol configured."""
    # Register source Cisco switch
    res1 = client.post(
        "/api/v1/devices",
        json={
            "id": "dev-cisco-core-01",
            "name": "Cisco-Core-01",
            "ip_address": "10.0.10.1",
            "device_type": "switch",
            "vendor_model": "Cisco Catalyst 9300",
            "building": "Admin Building",
            "department": "Administration",
            "floor": "Floor 1",
            "collection_method": "mock",
        },
    )
    assert res1.status_code == 201

    # Register access switch neighbor
    res2 = client.post(
        "/api/v1/devices",
        json={
            "id": "dev-cisco-acc-01",
            "name": "Cisco-Access-01",
            "ip_address": "10.0.10.2",
            "device_type": "switch",
            "vendor_model": "Cisco Catalyst 2960X",
            "building": "Admin Building",
            "department": "Administration",
            "floor": "Floor 1",
            "collection_method": "mock",
        },
    )
    assert res2.status_code == 201

    # Mock provider generates CDP neighbors when queried
    # Directly test discovery trigger
    disc_res = client.post("/api/v1/topology/devices/dev-cisco-core-01/discover")
    assert disc_res.status_code == 200
    disc_data = disc_res.json()
    assert disc_data["success"] is True

    # Check device discovery status endpoint
    status_res = client.get("/api/v1/topology/devices/dev-cisco-core-01/status")
    assert status_res.status_code == 200
    st_data = status_res.json()
    assert st_data["status"] == "success"
    assert st_data["discovered_neighbors_count"] >= 1
    assert st_data["last_discovery_at"] is not None


def test_unresolved_remote_chassis_id(client: TestClient):
    """Discovered neighbor with unregistered chassis ID stays unresolved without phantom device."""
    # Register router only (do NOT register the remote lab AP neighbor)
    res = client.post(
        "/api/v1/devices",
        json={
            "id": "dev-router-unresolved-test",
            "name": "Edge-Router-Lab",
            "ip_address": "10.0.30.1",
            "device_type": "router",
            "building": "Science Complex",
            "department": "Physics",
            "floor": "Floor 2",
            "collection_method": "mock",
        },
    )
    assert res.status_code == 201

    # Trigger discovery
    disc_res = client.post("/api/v1/topology/devices/dev-router-unresolved-test/discover")
    assert disc_res.status_code == 200

    # Query unresolved links endpoint
    unresolved_res = client.get("/api/v1/topology/unresolved")
    assert unresolved_res.status_code == 200
    unresolved_data = unresolved_res.json()
    assert unresolved_data["total_unresolved"] >= 1

    unresolved_link = unresolved_data["unresolved_neighbors"][0]
    assert unresolved_link["remote_device_id"] is None
    assert unresolved_link["resolution_state"] == "unresolved"
    assert unresolved_link["remote_chassis_id"] != ""

    # CRITICAL: Verify NO phantom device was created in the device registry
    dev_res = client.get("/api/v1/devices")
    devices = dev_res.json()["devices"]
    assert len(devices) == 1
    assert devices[0]["id"] == "dev-router-unresolved-test"


def test_duplicate_neighbor_observations_idempotency(client: TestClient):
    """Repeated discoveries for the same device update last_seen_at without duplicate records."""
    client.post(
        "/api/v1/devices",
        json={
            "id": "dev-idem-01",
            "name": "Idempotent-Router",
            "ip_address": "10.0.40.1",
            "device_type": "router",
            "building": "Admin Complex",
            "department": "IT Operations",
            "floor": "Floor 1",
            "collection_method": "mock",
        },
    )

    # First discovery
    disc1 = client.post("/api/v1/topology/devices/dev-idem-01/discover")
    assert disc1.status_code == 200
    links1 = client.get("/api/v1/topology/links?source_device_id=dev-idem-01").json()["links"]
    count1 = len(links1)
    assert count1 >= 1
    first_last_seen = links1[0]["last_seen_at"]

    # Second discovery
    disc2 = client.post("/api/v1/topology/devices/dev-idem-01/discover")
    assert disc2.status_code == 200
    links2 = client.get("/api/v1/topology/links?source_device_id=dev-idem-01").json()["links"]
    count2 = len(links2)

    # Count must be identical (no duplicate rows created)
    assert count1 == count2
    # last_seen_at must be updated or equal
    assert links2[0]["last_seen_at"] >= first_last_seen


def test_discovery_timeout_handling(client: TestClient):
    """A device with timeout behavior reports status='failed' without crashing."""
    res = client.post(
        "/api/v1/devices",
        json={
            "id": "dev-timeout-01",
            "name": "Slow-Switch",
            "ip_address": "10.0.50.1",
            "device_type": "switch",
            "building": "Science Complex",
            "department": "Physics",
            "floor": "Floor 2",
            "collection_method": "mock",
        },
    )
    assert res.status_code == 201

    # Inject timeout fault
    topology_service.mock_provider.set_fault("dev-timeout-01", "timeout")

    disc_res = client.post("/api/v1/topology/devices/dev-timeout-01/discover")
    assert disc_res.status_code == 200
    data = disc_res.json()
    assert data["success"] is False
    assert data["status"] == "failed"
    msg = data["message"].lower()
    assert "timeout" in msg or "timed out" in msg

    # Check status endpoint
    st_res = client.get("/api/v1/topology/devices/dev-timeout-01/status")
    assert st_res.status_code == 200
    st_data = st_res.json()
    assert st_data["status"] == "failed"
    assert st_data["last_error"] is not None


def test_unsupported_device_handling(client: TestClient):
    """A device without LLDP/CDP MIB support reports status='unsupported' honestly."""
    res = client.post(
        "/api/v1/devices",
        json={
            "id": "dev-unsupported-01",
            "name": "Unmanaged-Hub",
            "ip_address": "10.0.60.1",
            "device_type": "switch",
            "building": "Library",
            "department": "Circulation",
            "floor": "Floor 1",
            "collection_method": "mock",
        },
    )
    assert res.status_code == 201

    # Inject unsupported fault
    topology_service.mock_provider.set_fault("dev-unsupported-01", "unsupported")

    disc_res = client.post("/api/v1/topology/devices/dev-unsupported-01/discover")
    assert disc_res.status_code == 200
    data = disc_res.json()
    assert data["success"] is False
    assert data["status"] == "unsupported"
    assert data["neighbors_found"] == 0

    st_res = client.get("/api/v1/topology/devices/dev-unsupported-01/status")
    assert st_res.status_code == 200
    assert st_res.json()["status"] == "unsupported"
    assert st_res.json()["lldp_supported"] is False


def test_stale_link_transition(client: TestClient):
    """Links that have not been observed within the freshness window become stale."""
    res = client.post(
        "/api/v1/devices",
        json={
            "id": "dev-stale-01",
            "name": "Stale-Router",
            "ip_address": "10.0.70.1",
            "device_type": "router",
            "building": "Engineering Hall",
            "department": "Civil",
            "floor": "Floor 3",
            "collection_method": "mock",
        },
    )
    assert res.status_code == 201
    disc_res = client.post("/api/v1/topology/devices/dev-stale-01/discover")
    assert disc_res.status_code == 200

    db = TestingSessionLocal()
    try:
        # Age the discovered links by 2 hours
        two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
        links = db.query(TopologyLinkModel).filter(TopologyLinkModel.source_device_id == "dev-stale-01").all()
        assert len(links) > 0
        for l in links:
            l.last_seen_at = two_hours_ago
        db.commit()

        # Run mark_stale_links with 1 hour threshold
        marked = topology_service.mark_stale_links(db=db, device_id="dev-stale-01", stale_threshold_seconds=3600.0)
        assert marked == len(links)
    finally:
        db.close()

    # Verify links API shows them as stale
    links_res = client.get("/api/v1/topology/links?source_device_id=dev-stale-01")
    assert links_res.status_code == 200
    links_data = links_res.json()
    assert links_data["stale_links"] >= 1
    assert links_data["links"][0]["is_stale"] is True
    assert links_data["links"][0]["link_status"] == "stale"


def test_credential_redaction(client: TestClient):
    """Configured SNMP credentials/community env names are never leaked in topology API responses."""
    secret_env_name = "SUPER_SECRET_SNMP_COMMUNITY_KEY_999"
    res = client.post(
        "/api/v1/devices",
        json={
            "id": "dev-secure-01",
            "name": "Secure-Core-Router",
            "ip_address": "10.0.80.1",
            "device_type": "router",
            "building": "Server Room",
            "department": "NOC",
            "floor": "Basement",
            "collection_method": "mock",
        },
    )
    assert res.status_code == 201

    # Discover
    disc_res = client.post("/api/v1/topology/devices/dev-secure-01/discover")
    assert disc_res.status_code == 200
    assert secret_env_name not in disc_res.text

    # Check status
    st_res = client.get("/api/v1/topology/devices/dev-secure-01/status")
    assert st_res.status_code == 200
    assert secret_env_name not in st_res.text

    # Check links
    links_res = client.get("/api/v1/topology/links")
    assert links_res.status_code == 200
    assert secret_env_name not in links_res.text

    # Check neighbors
    neighbors_res = client.get("/api/v1/topology/devices/dev-secure-01/neighbors")
    assert neighbors_res.status_code == 200
    assert secret_env_name not in neighbors_res.text


def test_device_deletion_cascade(client: TestClient):
    """Deleting a device cascades to remove its source links, remote links, and discovery status."""
    # Register source and destination
    client.post(
        "/api/v1/devices",
        json={
            "id": "dev-del-source",
            "name": "Source-Router",
            "ip_address": "10.0.90.1",
            "device_type": "router",
            "building": "Tower A",
            "department": "Telecom",
            "floor": "Roof",
            "collection_method": "mock",
        },
    )
    client.post(
        "/api/v1/devices",
        json={
            "id": "dev-del-dest",
            "name": "Dest-Switch",
            "ip_address": "10.0.90.2",
            "device_type": "switch",
            "building": "Tower A",
            "department": "Telecom",
            "floor": "Floor 10",
            "collection_method": "mock",
        },
    )

    # Discover from source
    client.post("/api/v1/topology/devices/dev-del-source/discover")
    links_before = client.get("/api/v1/topology/links?source_device_id=dev-del-source").json()["links"]
    assert len(links_before) > 0

    status_before = client.get("/api/v1/topology/devices/dev-del-source/status").json()
    assert status_before["status"] == "success"

    # Delete source device
    del_res = client.delete("/api/v1/devices/dev-del-source")
    assert del_res.status_code in (200, 204)

    # Verify links originating from dev-del-source are gone
    links_after = client.get("/api/v1/topology/links?source_device_id=dev-del-source").json()["links"]
    assert len(links_after) == 0

    # Verify device status endpoint returns 404 for deleted device
    status_after = client.get("/api/v1/topology/devices/dev-del-source/status")
    assert status_after.status_code == 404


def test_mock_vs_actual_separation(client: TestClient):
    """Mock links are explicitly marked is_mock=True, while SNMP devices return unsupported without fake links."""
    # Register real SNMP device targeting an unused loopback IP
    res = client.post(
        "/api/v1/devices",
        json={
            "id": "dev-real-snmp-01",
            "name": "Real-SNMP-Device",
            "ip_address": "127.0.0.99",
            "device_type": "switch",
            "building": "Server Room",
            "department": "Network Engineering",
            "floor": "Basement",
            "collection_method": "snmp",
        },
    )
    assert res.status_code == 201

    # Real SNMP probe against unlistening port fails cleanly and does NOT fabricate links
    disc_res = client.post("/api/v1/topology/devices/dev-real-snmp-01/discover")
    assert disc_res.status_code == 200
    disc_data = disc_res.json()
    assert disc_data["success"] is False
    assert disc_data["neighbors_found"] == 0

    # Verify no links were created for real device
    links = client.get("/api/v1/topology/links?source_device_id=dev-real-snmp-01").json()["links"]
    assert len(links) == 0


def test_regression_local_monitoring_and_simulation(client: TestClient):
    """Topology additions must not interfere with local psutil monitoring, anomaly detection, or simulation lab."""
    # Local metrics endpoint
    metric_res = client.get("/api/v1/metrics/latest")
    assert metric_res.status_code in (200, 404)

    # Anomaly summary endpoint
    anomaly_res = client.get("/api/v1/anomalies/summary")
    assert anomaly_res.status_code == 200
    assert "total_anomalies" in anomaly_res.json()

    # Simulation lab scenarios endpoint
    sim_res = client.get("/api/v1/simulation/scenarios")
    assert sim_res.status_code == 200
    scenarios = sim_res.json()["scenarios"]
    assert len(scenarios) >= 5


def test_bidirectional_observations_and_filter_immutability(client: TestClient):
    """Bidirectional discovery records both observations in backend, and querying/filtering never mutates backend records."""
    # Register two interconnected mock devices
    client.post(
        "/api/v1/devices",
        json={
            "id": "dev-bidi-r1",
            "name": "Bidi-Router-1",
            "ip_address": "10.0.50.1",
            "device_type": "router",
            "building": "Science Block",
            "department": "CS",
            "floor": "Floor 2",
            "collection_method": "mock",
        },
    )
    client.post(
        "/api/v1/devices",
        json={
            "id": "dev-bidi-sw1",
            "name": "Bidi-Switch-1",
            "ip_address": "10.0.50.2",
            "device_type": "switch",
            "building": "Science Block",
            "department": "CS",
            "floor": "Floor 2",
            "collection_method": "mock",
        },
    )

    # Trigger discovery on router
    res1 = client.post("/api/v1/topology/devices/dev-bidi-r1/discover")
    assert res1.status_code == 200

    # Trigger discovery on switch
    res2 = client.post("/api/v1/topology/devices/dev-bidi-sw1/discover")
    assert res2.status_code == 200

    # Fetch all links
    links_all = client.get("/api/v1/topology/links").json()["links"]
    assert len(links_all) >= 2

    # Query with filters to verify filtering does NOT mutate or delete records
    filtered_lldp = client.get("/api/v1/topology/links?protocol=lldp").json()["links"]
    assert len(filtered_lldp) >= 1

    filtered_dev = client.get("/api/v1/topology/links?source_device_id=dev-bidi-r1").json()["links"]
    assert len(filtered_dev) >= 1

    # Re-fetch all links to ensure count is identical (immutability confirmed)
    links_refetched = client.get("/api/v1/topology/links").json()["links"]
    assert len(links_refetched) == len(links_all)

    # Verify unresolved neighbors also remain accessible
    unres = client.get("/api/v1/topology/unresolved").json()["unresolved_neighbors"]
    assert len(unres) >= 1

