"""End-to-end integration and demonstration test for Phase 7.

Validates the complete 9-step demo workflow:
1. Four mock devices registered in campus registry.
2. Topology discovery executed against core switch.
3. Neighbors include both a resolved campus device and an unresolved neighbor.
4. New topology alerts generated with status 'open'.
5. Operator acknowledges an alert with a comment (status -> 'acknowledged').
6. Neighbor exceeds freshness window and transitions to 'stale' ('neighbor_stale' alert generated).
7. Neighbor renews advertisements and restores to 'active' ('neighbor_restored' alert generated).
8. The previous 'neighbor_stale' alert is automatically resolved by the engine.
9. Historical audit trail verifies resolved, acknowledged, and open alerts are preserved.
"""

from datetime import datetime, timezone, timedelta
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
from app.services.topology import topology_service, DiscoveredNeighbor

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
    with TestClient(app) as c:
        yield c


def test_complete_phase7_demo_workflow(client: TestClient):
    """Execute the complete 9-step end-to-end demonstration workflow."""

    # ------------------------------------------------------------------------
    # Step 1: Register Four Mock Campus Devices
    # ------------------------------------------------------------------------
    demo_devices = [
        {
            "id": "demo-core-01",
            "name": "Campus-Core-Switch",
            "ip_address": "10.0.1.1",
            "device_type": "switch",
            "building": "Main Administration",
            "floor": "Floor 1",
            "department": "IT Operations",
            "collection_method": "mock",
            "vendor_model": "Cisco Catalyst 9500",
        },
        {
            "id": "demo-dist-01",
            "name": "Science-Dist-Switch",
            "ip_address": "10.0.2.1",
            "device_type": "switch",
            "building": "Science Hall",
            "floor": "Floor 2",
            "department": "Physics",
            "collection_method": "mock",
            "vendor_model": "Cisco Catalyst 9300",
        },
        {
            "id": "demo-edge-01",
            "name": "Engineering-Edge-Switch",
            "ip_address": "10.0.3.1",
            "device_type": "switch",
            "building": "Engineering Block",
            "floor": "Floor 1",
            "department": "ECE",
            "collection_method": "mock",
            "vendor_model": "Aruba CX 6300",
        },
        {
            "id": "demo-gw-01",
            "name": "Campus-Gateway-Router",
            "ip_address": "10.0.0.1",
            "device_type": "router",
            "building": "Data Center",
            "floor": "Basement",
            "department": "IT Operations",
            "collection_method": "mock",
            "vendor_model": "Cisco ISR 4451",
        },
    ]

    for dev_payload in demo_devices:
        res = client.post("/api/v1/devices", json=dev_payload)
        assert res.status_code == 201, f"Failed to register {dev_payload['name']}: {res.text}"

    # Verify device list has exactly 4 devices
    dev_list_res = client.get("/api/v1/devices")
    assert dev_list_res.status_code == 200
    assert dev_list_res.json()["total"] == 4

    # ------------------------------------------------------------------------
    # Step 2: Configure and Trigger Topology Discovery on demo-core-01
    # ------------------------------------------------------------------------
    # Configure deterministic mock topology for demo-core-01:
    # 1. Neighbor 1: Science-Dist-Switch (Resolved to registered device demo-dist-01)
    # 2. Neighbor 2: External unmanaged AP (Unresolved neighbor)
    topology_service.mock_provider._mock_topologies["demo-core-01"] = [
        DiscoveredNeighbor(
            local_interface="GigabitEthernet0/1",
            remote_chassis_id="00:1A:2B:CC:DD:01",
            remote_chassis_id_subtype="mac_address",
            remote_port_id="GigabitEthernet0/24",
            remote_port_id_subtype="interface_name",
            remote_port_desc="Uplink to Science Dist",
            remote_system_name="Science-Dist-Switch",
            remote_system_desc="Cisco Catalyst 9300",
            protocol="cdp",
            discovery_source="mock",
            raw_address="10.0.2.1",
        ),
        DiscoveredNeighbor(
            local_interface="GigabitEthernet0/2",
            remote_chassis_id="00:50:56:AA:BB:CC",
            remote_chassis_id_subtype="mac_address",
            remote_port_id="eth0",
            remote_port_id_subtype="interface_name",
            remote_port_desc="Unmanaged Visitor AP",
            remote_system_name="unregistered-guest-ap",
            remote_system_desc="Aruba Instant On AP22",
            protocol="lldp",
            discovery_source="mock",
            raw_address="192.168.99.200",
        ),
    ]

    disc_res = client.post("/api/v1/topology/devices/demo-core-01/discover")
    assert disc_res.status_code == 200
    disc_data = disc_res.json()
    assert disc_data["success"] is True
    assert disc_data["neighbors_found"] == 2
    assert disc_data["neighbors_resolved"] == 1  # 1 resolved, 1 unresolved

    # ------------------------------------------------------------------------
    # Step 3: Verify Resolved and Unresolved Neighbors
    # ------------------------------------------------------------------------
    links_res = client.get("/api/v1/topology/links?source_device_id=demo-core-01")
    assert links_res.status_code == 200
    links_data = links_res.json()
    assert links_data["total_links"] == 2
    assert links_data["resolved_links"] == 1
    assert links_data["unresolved_links"] == 1

    resolved_link = next(l for l in links_data["links"] if l["resolution_state"] == "resolved")
    unresolved_link = next(l for l in links_data["links"] if l["resolution_state"] == "unresolved")

    assert resolved_link["remote_device_id"] == "demo-dist-01"
    assert resolved_link["remote_system_name"] == "Science-Dist-Switch"
    assert unresolved_link["remote_device_id"] is None
    assert unresolved_link["remote_system_name"] == "unregistered-guest-ap"

    # ------------------------------------------------------------------------
    # Step 4: Verify New Topology Alerts Created with Status 'open'
    # ------------------------------------------------------------------------
    alerts_res = client.get("/api/v1/alerts?device_id=demo-core-01&status=open")
    assert alerts_res.status_code == 200
    alerts_data = alerts_res.json()
    assert alerts_data["open_count"] == 2

    ap_alert = next(
        a for a in alerts_data["alerts"] if a["local_interface"] == "GigabitEthernet0/2"
    )
    dist_alert = next(
        a for a in alerts_data["alerts"] if a["local_interface"] == "GigabitEthernet0/1"
    )
    assert ap_alert["event_type"] == "new_neighbor"
    assert ap_alert["status"] == "open"
    assert ap_alert["is_mock"] is True  # Rule 4 & 6 honest representation

    # ------------------------------------------------------------------------
    # Step 5: Acknowledge the Unmanaged AP Alert
    # ------------------------------------------------------------------------
    ack_res = client.post(
        f"/api/v1/alerts/{ap_alert['id']}/acknowledge",
        json={
            "acknowledged_by": "Senior Network Admin",
            "note": "Verified authorized temporary visitor AP installation",
        },
    )
    assert ack_res.status_code == 200
    ack_data = ack_res.json()
    assert ack_data["status"] == "acknowledged"
    assert ack_data["acknowledged_by"] == "Senior Network Admin"
    assert ack_data["acknowledgement_note"] == "Verified authorized temporary visitor AP installation"

    # ------------------------------------------------------------------------
    # Step 6: Neighbor Exceeds Freshness Window -> Stale Observation Alert
    # ------------------------------------------------------------------------
    db = TestingSessionLocal()
    try:
        # Age the resolved link beyond the freshness window
        link_to_age = db.query(TopologyLinkModel).filter(
            TopologyLinkModel.source_device_id == "demo-core-01",
            TopologyLinkModel.local_interface == "GigabitEthernet0/1",
        ).first()
        link_to_age.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=600)
        db.commit()

        # Run mark_stale_links()
        staled_count = topology_service.mark_stale_links(db=db, stale_threshold_seconds=300)
        assert staled_count == 1
    finally:
        db.close()

    # Verify neighbor_stale alert was generated
    stale_alerts_res = client.get("/api/v1/alerts?event_type=neighbor_stale&status=open")
    assert stale_alerts_res.status_code == 200
    stale_alerts = stale_alerts_res.json()["alerts"]
    assert len(stale_alerts) == 1
    stale_alert = stale_alerts[0]
    assert stale_alert["source_device_id"] == "demo-core-01"
    assert stale_alert["local_interface"] == "GigabitEthernet0/1"
    # Rule 7 non-negotiable check: Message states unrefreshed, not physical failure
    assert "not confirmed line failure" in stale_alert["message"].lower()

    # ------------------------------------------------------------------------
    # Step 7: Neighbor Renews Advertisements -> Neighbor Restoration
    # ------------------------------------------------------------------------
    # Next discovery cycle receives renewed advertisement on Gi0/1
    disc_renew_res = client.post("/api/v1/topology/devices/demo-core-01/discover")
    assert disc_renew_res.status_code == 200

    # Verify link returned to active
    active_links_res = client.get(
        "/api/v1/topology/links?source_device_id=demo-core-01&link_status=active"
    )
    assert active_links_res.status_code == 200
    assert active_links_res.json()["total_links"] == 2

    # Verify neighbor_restored alert created
    restored_res = client.get("/api/v1/alerts?event_type=neighbor_restored")
    assert restored_res.status_code == 200
    assert len(restored_res.json()["alerts"]) == 1

    # ------------------------------------------------------------------------
    # Step 8: Verify Stale Alert Was Automatically Resolved
    # ------------------------------------------------------------------------
    auto_res = client.get(f"/api/v1/alerts/{stale_alert['id']}")
    assert auto_res.status_code == 200
    auto_data = auto_res.json()
    assert auto_data["status"] == "resolved"
    assert auto_data["resolved_by"] == "System (Auto-recovery)"
    assert auto_data["resolved_at"] is not None

    # ------------------------------------------------------------------------
    # Step 9: Alert History and Summary Audit Trail
    # ------------------------------------------------------------------------
    summary_res = client.get("/api/v1/alerts/summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["total_alerts"] >= 3
    assert summary["acknowledged_alerts"] >= 1
    assert summary["resolved_alerts"] >= 1
    assert summary["mock_alerts_count"] == summary["total_alerts"]  # All labeled mock
    assert summary["actual_alerts_count"] == 0  # Zero unverified SNMP claims

    # Cleanup mock topology override
    topology_service.mock_provider._mock_topologies.pop("demo-core-01", None)
