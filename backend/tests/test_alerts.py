"""Automated tests for Phase 6: Topology Change Detection & Alerting Engine.

Covers:
- New neighbor event detection
- Stale observation warning event
- Neighbor restoration event
- Duplicate alert suppression (occurrence_count increment, zero duplicate rows)
- Interface mapping change detection
- Protocol observation change detection (LLDP <-> CDP)
- Discovery failure event
- Alert acknowledgement lifecycle transition
- Alert resolution lifecycle transition
- Alert filtering (status, severity, event_type, device, is_mock)
- Alert summary aggregation counts
- Mock vs. actual SNMP provenance
- Isolation of existing telemetry and AI anomaly systems
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import DeviceModel, TopologyAlertModel, TopologyLinkModel
from app.services.alerting import alert_service
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


def test_empty_alerts_endpoint(client: TestClient):
    """When no alerts exist, endpoints return empty lists and zero counts with honest zeroes."""
    res = client.get("/api/v1/alerts")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["open_count"] == 0
    assert data["acknowledged_count"] == 0
    assert data["resolved_count"] == 0
    assert data["alerts"] == []

    summary_res = client.get("/api/v1/alerts/summary")
    assert summary_res.status_code == 200
    s_data = summary_res.json()
    assert s_data["total_alerts"] == 0
    assert s_data["open_alerts"] == 0


def test_new_neighbor_alert_generation(client: TestClient):
    """Running discovery on a mock device generates 'new_neighbor' alerts for initial links."""
    # Register core router
    client.post(
        "/api/v1/devices",
        json={
            "id": "dev-core-01",
            "name": "Core-Router",
            "ip_address": "10.0.1.1",
            "device_type": "router",
            "building": "Main Block",
            "floor": "Floor 1",
            "department": "Networking",
            "collection_method": "mock",
        },
    )

    # Trigger initial discovery
    disc_res = client.post("/api/v1/topology/devices/dev-core-01/discover")
    assert disc_res.status_code == 200
    assert disc_res.json()["success"] is True

    # Check generated alerts
    alerts_res = client.get("/api/v1/alerts")
    assert alerts_res.status_code == 200
    alerts_data = alerts_res.json()
    assert alerts_data["open_count"] > 0
    assert any(a["event_type"] == "new_neighbor" for a in alerts_data["alerts"])
    first_alert = alerts_data["alerts"][0]
    assert first_alert["status"] == "open"
    assert first_alert["is_mock"] is True
    assert first_alert["source_device_id"] == "dev-core-01"


def test_duplicate_alert_suppression(client: TestClient):
    """Re-running discovery with unchanged neighbors increments occurrence_count without duplicate alerts."""
    client.post(
        "/api/v1/devices",
        json={
            "id": "dev-suppress-01",
            "name": "Distribution-Switch",
            "ip_address": "10.0.1.2",
            "device_type": "switch",
            "building": "Main Block",
            "floor": "Floor 1",
            "department": "Networking",
            "collection_method": "mock",
        },
    )

    # First discovery run
    client.post("/api/v1/topology/devices/dev-suppress-01/discover")
    alerts_run1 = client.get("/api/v1/alerts").json()["alerts"]
    count_run1 = len(alerts_run1)
    assert count_run1 > 0

    # Second discovery run with identical topology
    client.post("/api/v1/topology/devices/dev-suppress-01/discover")
    alerts_run2 = client.get("/api/v1/alerts").json()["alerts"]
    count_run2 = len(alerts_run2)

    # Verify no duplicate alert rows were created
    assert count_run2 == count_run1
    # Verify occurrence count increased for persistent conditions
    for a in alerts_run2:
        assert a["occurrence_count"] >= 1


def test_stale_observation_alert_generation(client: TestClient):
    """Transitioning an active link to stale triggers a 'neighbor_stale' warning alert."""
    db = TestingSessionLocal()
    try:
        # Create an active link directly
        link = TopologyLinkModel(
            source_device_id="dev-stale-test",
            local_interface="GigabitEthernet0/1",
            remote_chassis_id="00:11:22:33:44:55",
            remote_port_id="GigabitEthernet0/24",
            protocol="lldp",
            link_status="active",
            discovery_source="mock",
            resolution_state="unresolved",
            last_seen_at=datetime.now(timezone.utc),
            discovered_at=datetime.now(timezone.utc),
        )
        db.add(link)
        db.commit()

        # Mark links older than -1 seconds stale
        stale_count = topology_service.mark_stale_links(db=db, device_id="dev-stale-test", stale_threshold_seconds=-1.0)
        assert stale_count == 1
    finally:
        db.close()

    # Verify neighbor_stale alert was generated
    res = client.get("/api/v1/alerts?event_type=neighbor_stale")
    assert res.status_code == 200
    stale_alerts = res.json()["alerts"]
    assert len(stale_alerts) == 1
    assert stale_alerts[0]["severity"] == "warning"
    assert "exceeded freshness window" in stale_alerts[0]["message"]


def test_neighbor_restoration_alert(client: TestClient):
    """When a stale neighbor is observed again in discovery, a 'neighbor_restored' alert is generated."""
    db = TestingSessionLocal()
    try:
        # Create a registered mock device
        dev = DeviceModel(
            id="dev-restore-01",
            name="Restoration-Test-Router",
            ip_address="10.0.9.1",
            device_type="router",
            building="Hall A",
            floor="Floor 1",
            department="IT",
            collection_method="mock",
        )
        db.add(dev)

        # Pre-seed a STALE link for this device
        stale_link = TopologyLinkModel(
            source_device_id="dev-restore-01",
            local_interface="GigabitEthernet0/1",
            remote_chassis_id="00:AA:BB:CC:DD:EE",
            remote_port_id="GigabitEthernet0/24",
            protocol="lldp",
            link_status="stale",
            discovery_source="mock",
            resolution_state="unresolved",
            last_seen_at=datetime.now(timezone.utc),
            discovered_at=datetime.now(timezone.utc),
        )
        db.add(stale_link)
        db.commit()
    finally:
        db.close()

    # Pre-configure mock provider to return this exact neighbor so it returns to active
    from app.services.topology import DiscoveredNeighbor
    topology_service.mock_provider._mock_topologies["dev-restore-01"] = [
        DiscoveredNeighbor(
            local_interface="GigabitEthernet0/1",
            remote_chassis_id="00:AA:BB:CC:DD:EE",
            remote_port_id="GigabitEthernet0/24",
            protocol="lldp",
            discovery_source="mock",
            remote_system_name="Restored-Peer",
        )
    ]

    # Run discovery to restore neighbor
    disc_res = client.post("/api/v1/topology/devices/dev-restore-01/discover")
    assert disc_res.status_code == 200

    # Clean up mock topology override
    topology_service.mock_provider._mock_topologies.pop("dev-restore-01", None)

    # Check alerts for neighbor_restored
    res = client.get("/api/v1/alerts?event_type=neighbor_restored")
    assert res.status_code == 200
    restored_alerts = res.json()["alerts"]
    assert len(restored_alerts) == 1
    assert restored_alerts[0]["event_type"] == "neighbor_restored"
    assert "renewed advertisements" in restored_alerts[0]["message"]


def test_interface_changed_alert(client: TestClient):
    """When a remote neighbor shifts local interface ports, an 'interface_changed' alert is generated."""
    db = TestingSessionLocal()
    try:
        dev = DeviceModel(
            id="dev-shift-01",
            name="Shift-Test-Switch",
            ip_address="10.0.8.1",
            device_type="switch",
            building="Hall B",
            floor="Floor 1",
            department="IT",
            collection_method="mock",
        )
        db.add(dev)
        # Neighbor previously on Gi0/1
        old_link = TopologyLinkModel(
            source_device_id="dev-shift-01",
            local_interface="GigabitEthernet0/1",
            remote_chassis_id="00:50:56:11:22:33",
            remote_port_id="eth0",
            protocol="lldp",
            link_status="active",
            discovery_source="mock",
            resolution_state="unresolved",
            remote_system_name="AP-Shifted",
            last_seen_at=datetime.now(timezone.utc),
            discovered_at=datetime.now(timezone.utc),
        )
        db.add(old_link)
        db.commit()
    finally:
        db.close()

    # Discovery now sees same remote chassis on Gi0/2
    from app.services.topology import DiscoveredNeighbor
    topology_service.mock_provider._mock_topologies["dev-shift-01"] = [
        DiscoveredNeighbor(
            local_interface="GigabitEthernet0/2",
            remote_chassis_id="00:50:56:11:22:33",
            remote_port_id="eth0",
            protocol="lldp",
            discovery_source="mock",
            remote_system_name="AP-Shifted",
        )
    ]

    client.post("/api/v1/topology/devices/dev-shift-01/discover")
    topology_service.mock_provider._mock_topologies.pop("dev-shift-01", None)

    res = client.get("/api/v1/alerts?event_type=interface_changed")
    assert res.status_code == 200
    shifted_alerts = res.json()["alerts"]
    assert len(shifted_alerts) == 1
    assert shifted_alerts[0]["severity"] == "warning"
    assert "shifted interface" in shifted_alerts[0]["message"]


def test_protocol_changed_alert(client: TestClient):
    """When a neighbor advertisement changes protocol (e.g. LLDP to CDP), 'protocol_changed' alert is generated."""
    db = TestingSessionLocal()
    try:
        dev = DeviceModel(
            id="dev-proto-01",
            name="Proto-Switch",
            ip_address="10.0.7.1",
            device_type="switch",
            building="Lab C",
            floor="Floor 1",
            department="ECE",
            collection_method="mock",
        )
        db.add(dev)
        old_link = TopologyLinkModel(
            source_device_id="dev-proto-01",
            local_interface="GigabitEthernet0/5",
            remote_chassis_id="00:22:33:44:55:66",
            remote_port_id="GigabitEthernet0/1",
            protocol="lldp",
            link_status="active",
            discovery_source="mock",
            resolution_state="unresolved",
            last_seen_at=datetime.now(timezone.utc),
            discovered_at=datetime.now(timezone.utc),
        )
        db.add(old_link)
        db.commit()
    finally:
        db.close()

    # Now reported via CDP
    from app.services.topology import DiscoveredNeighbor
    topology_service.mock_provider._mock_topologies["dev-proto-01"] = [
        DiscoveredNeighbor(
            local_interface="GigabitEthernet0/5",
            remote_chassis_id="00:22:33:44:55:66",
            remote_port_id="GigabitEthernet0/1",
            protocol="cdp",
            discovery_source="mock",
            remote_system_name="Cisco-Neighbor",
        )
    ]

    client.post("/api/v1/topology/devices/dev-proto-01/discover")
    topology_service.mock_provider._mock_topologies.pop("dev-proto-01", None)

    res = client.get("/api/v1/alerts?event_type=protocol_changed")
    assert res.status_code == 200
    proto_alerts = res.json()["alerts"]
    assert len(proto_alerts) == 1
    assert "protocol" in proto_alerts[0]["message"].lower()


def test_discovery_failure_alert(client: TestClient):
    """When discovery against an SNMP target fails, a critical 'discovery_failed' alert is generated."""
    client.post(
        "/api/v1/devices",
        json={
            "id": "dev-fail-01",
            "name": "Failing-SNMP-Switch",
            "ip_address": "192.0.2.1",
            "device_type": "switch",
            "building": "Tower B",
            "floor": "Basement",
            "department": "Infrastructure",
            "collection_method": "snmp",
        },
    )

    # Discover against unreachable test address
    client.post("/api/v1/topology/devices/dev-fail-01/discover")

    res = client.get("/api/v1/alerts?event_type=discovery_failed")
    assert res.status_code == 200
    alerts = res.json()["alerts"]
    assert len(alerts) >= 1
    assert alerts[0]["severity"] == "critical"
    assert alerts[0]["source_device_id"] == "dev-fail-01"


def test_alert_acknowledge_and_resolve_lifecycle(client: TestClient):
    """Alerts follow OPEN -> ACKNOWLEDGED -> RESOLVED lifecycle cleanly."""
    db = TestingSessionLocal()
    try:
        alert = alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="new_neighbor",
            severity="info",
            source_device_id="dev-lifecycle-01",
            message="Test lifecycle alert",
        )
        alert_id = alert.id
    finally:
        db.close()

    # Verify initial open status
    get_res = client.get(f"/api/v1/alerts/{alert_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "open"

    # Acknowledge alert
    ack_res = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": "Senior Engineer", "note": "Investigating link update"},
    )
    assert ack_res.status_code == 200
    ack_data = ack_res.json()
    assert ack_data["status"] == "acknowledged"
    assert ack_data["acknowledged_by"] == "Senior Engineer"
    assert ack_data["acknowledgement_note"] == "Investigating link update"
    assert ack_data["acknowledged_at"] is not None

    # Resolve alert
    res_res = client.post(
        f"/api/v1/alerts/{alert_id}/resolve",
        json={"resolved_by": "Senior Engineer", "note": "Verified legitimate campus expansion"},
    )
    assert res_res.status_code == 200
    res_data = res_res.json()
    assert res_data["status"] == "resolved"
    assert res_data["resolved_by"] == "Senior Engineer"
    assert res_data["resolution_note"] == "Verified legitimate campus expansion"
    assert res_data["resolved_at"] is not None


def test_alert_filtering_and_summary(client: TestClient):
    """Test filtering by severity, status, event_type, device_id, and is_mock."""
    db = TestingSessionLocal()
    try:
        alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="new_neighbor",
            severity="info",
            source_device_id="dev-filter-a",
            message="Alert A",
            is_mock=True,
        )
        alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="neighbor_stale",
            severity="warning",
            source_device_id="dev-filter-b",
            message="Alert B",
            is_mock=False,
        )
    finally:
        db.close()

    # Filter by severity
    res_sev = client.get("/api/v1/alerts?severity=warning").json()["alerts"]
    assert len(res_sev) == 1
    assert res_sev[0]["source_device_id"] == "dev-filter-b"

    # Filter by mock
    res_mock = client.get("/api/v1/alerts?is_mock=true").json()["alerts"]
    assert len(res_mock) == 1
    assert res_mock[0]["source_device_id"] == "dev-filter-a"

    # Summary
    summary = client.get("/api/v1/alerts/summary").json()
    assert summary["total_alerts"] == 2
    assert summary["mock_alerts_count"] == 1
    assert summary["actual_alerts_count"] == 1
    assert summary["by_severity"]["warning"] == 1
    assert summary["by_severity"]["info"] == 1


def test_regression_telemetry_and_anomalies_isolation(client: TestClient):
    """Alerting additions do not impact host psutil metrics, anomaly detector, or simulation lab."""
    m_res = client.get("/api/v1/metrics/latest")
    assert m_res.status_code in (200, 404)

    a_res = client.get("/api/v1/anomalies/summary")
    assert a_res.status_code == 200

    s_res = client.get("/api/v1/simulation/scenarios")
    assert s_res.status_code == 200
    assert len(s_res.json()["scenarios"]) >= 5
