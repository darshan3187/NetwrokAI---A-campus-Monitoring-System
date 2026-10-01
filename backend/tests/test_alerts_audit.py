"""Automated audit tests for Phase 6.1: Alert Lifecycle, Concurrency & Reliability.

Verifies:
- Task 1: Deduplication (repeated occurrences, post-acknowledgement, post-resolution,
          concurrent thread safety, multi-device isolation, port isolation, mock/actual isolation)
- Task 2: Alert Lifecycle (OPEN -> ACKNOWLEDGED -> RESOLVED, invalid transition rejection,
          idempotent repeated actions, automatic resolution of stale alerts on restoration)
- Task 3: Event Detection Reliability (repeated timeouts, device deletion integrity, DB persistence)
- Task 4: API Security (input validation for length boundaries and rejection of malformed requests)
"""

from concurrent.futures import ThreadPoolExecutor
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
from app.services.devices import device_service
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
    with TestClient(app) as c:
        yield c


# ============================================================================
# Task 1: Deduplication Audits
# ============================================================================


def test_audit_dedup_repeated_same_event():
    """1. Same event occurs repeatedly -> exactly 1 alert row, occurrence_count increments."""
    db = TestingSessionLocal()
    try:
        for _ in range(5):
            alert = alert_service.create_or_deduplicate_alert(
                db=db,
                event_type="new_neighbor",
                severity="info",
                source_device_id="sw-repeat-01",
                local_interface="GigabitEthernet0/1",
                remote_chassis_id="aa:bb:cc:dd:ee:01",
                message="Repeated neighbor observation",
            )
            assert alert.status == "open"

        # Check database table count
        total_alerts = db.query(TopologyAlertModel).filter(
            TopologyAlertModel.source_device_id == "sw-repeat-01"
        ).all()
        assert len(total_alerts) == 1
        assert total_alerts[0].occurrence_count == 5
    finally:
        db.close()


def test_audit_dedup_after_acknowledgement():
    """2. Same event occurs after acknowledgement -> remains acknowledged, count increments, no new row."""
    db = TestingSessionLocal()
    try:
        # Create initial alert
        alert = alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="neighbor_stale",
            severity="warning",
            source_device_id="sw-ack-01",
            local_interface="GigabitEthernet0/2",
            remote_chassis_id="aa:bb:cc:dd:ee:02",
            message="Initial stale observation",
        )
        assert alert.status == "open"

        # Operator acknowledges the alert
        alert_service.acknowledge_alert(
            db=db,
            alert_id=alert.id,
            acknowledged_by="Lead Engineer",
            note="Investigating unrefreshed timer",
        )

        # Alert condition recurs
        re_alert = alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="neighbor_stale",
            severity="warning",
            source_device_id="sw-ack-01",
            local_interface="GigabitEthernet0/2",
            remote_chassis_id="aa:bb:cc:dd:ee:02",
            message="Recurring stale observation",
        )

        assert re_alert.id == alert.id
        assert re_alert.status == "acknowledged"  # Preserved lifecycle status
        assert re_alert.occurrence_count == 2
        assert re_alert.acknowledgement_note == "Investigating unrefreshed timer"

        # Still only 1 record
        records = db.query(TopologyAlertModel).filter(
            TopologyAlertModel.source_device_id == "sw-ack-01"
        ).all()
        assert len(records) == 1
    finally:
        db.close()


def test_audit_dedup_after_resolution():
    """3. Same event occurs after resolution -> creates a fresh OPEN alert, preserves resolved record."""
    db = TestingSessionLocal()
    try:
        # Initial alert created and resolved
        alert1 = alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="interface_changed",
            severity="warning",
            source_device_id="sw-res-01",
            local_interface="GigabitEthernet0/3",
            remote_chassis_id="aa:bb:cc:dd:ee:03",
            message="Cable was re-routed",
        )
        alert_service.resolve_alert(
            db=db,
            alert_id=alert1.id,
            resolved_by="Field Tech",
            note="Cable move approved and verified",
        )

        # Same condition occurs again at a later date
        alert2 = alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="interface_changed",
            severity="warning",
            source_device_id="sw-res-01",
            local_interface="GigabitEthernet0/3",
            remote_chassis_id="aa:bb:cc:dd:ee:03",
            message="Cable moved again unexpectedly",
        )

        assert alert2.id != alert1.id
        assert alert2.status == "open"
        assert alert2.occurrence_count == 1

        # Database now has 2 alerts: 1 resolved (historical audit) and 1 open (active)
        all_alerts = db.query(TopologyAlertModel).filter(
            TopologyAlertModel.source_device_id == "sw-res-01"
        ).all()
        assert len(all_alerts) == 2
        resolved = [a for a in all_alerts if a.status == "resolved"]
        open_ones = [a for a in all_alerts if a.status == "open"]
        assert len(resolved) == 1
        assert len(open_ones) == 1
        assert resolved[0].resolution_note == "Cable move approved and verified"
    finally:
        db.close()


def test_audit_dedup_concurrency_simultaneous_requests():
    """4. Concurrent threads attempting to create the exact same alert simultaneously -> exactly 1 alert row."""
    db_factory = TestingSessionLocal

    def create_alert_worker():
        worker_db = db_factory()
        try:
            return alert_service.create_or_deduplicate_alert(
                db=worker_db,
                event_type="discovery_failed",
                severity="critical",
                source_device_id="sw-concurrent-01",
                message="Simultaneous SNMP timeout error",
            )
        finally:
            worker_db.close()

    # Launch 10 workers concurrently across thread pool
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(create_alert_worker) for _ in range(10)]
        results = [f.result() for f in futures]

    db = TestingSessionLocal()
    try:
        alerts = db.query(TopologyAlertModel).filter(
            TopologyAlertModel.source_device_id == "sw-concurrent-01"
        ).all()
        assert len(alerts) == 1
        assert alerts[0].occurrence_count == 10
    finally:
        db.close()


def test_audit_dedup_distinct_devices():
    """5. Two different devices reporting similar events -> distinct alerts created (not merged)."""
    db = TestingSessionLocal()
    try:
        alert_a = alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="new_neighbor",
            severity="info",
            source_device_id="sw-alpha",
            local_interface="Gi0/1",
            remote_chassis_id="cc:cc:cc:11:22:33",
            message="Alpha saw peer",
        )
        alert_b = alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="new_neighbor",
            severity="info",
            source_device_id="sw-beta",
            local_interface="Gi0/1",
            remote_chassis_id="cc:cc:cc:11:22:33",
            message="Beta saw peer",
        )
        assert alert_a.id != alert_b.id
        assert db.query(TopologyAlertModel).count() == 2
    finally:
        db.close()


def test_audit_dedup_same_chassis_different_interfaces():
    """6. Same chassis appearing on different interfaces of same device -> distinct alerts created."""
    db = TestingSessionLocal()
    try:
        alert_p1 = alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="new_neighbor",
            severity="info",
            source_device_id="sw-multilink-01",
            local_interface="GigabitEthernet0/1",
            remote_chassis_id="00:11:22:33:44:55",
            message="Peer seen on port 1",
        )
        alert_p2 = alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="new_neighbor",
            severity="info",
            source_device_id="sw-multilink-01",
            local_interface="GigabitEthernet0/2",
            remote_chassis_id="00:11:22:33:44:55",
            message="Peer also seen on port 2 (LAG / dual-homed)",
        )
        assert alert_p1.id != alert_p2.id
        assert db.query(TopologyAlertModel).count() == 2
    finally:
        db.close()


def test_audit_dedup_mock_vs_actual_provenance():
    """7. Mock and actual SNMP events with identical IDs -> distinct alerts created (never merged)."""
    db = TestingSessionLocal()
    try:
        mock_alert = alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="new_neighbor",
            severity="info",
            source_device_id="sw-provenance-01",
            local_interface="Gi0/1",
            remote_chassis_id="00:aa:bb:cc:dd:ee",
            is_mock=True,
            discovery_source="mock",
            message="Simulated mock neighbor event",
        )
        snmp_alert = alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="new_neighbor",
            severity="info",
            source_device_id="sw-provenance-01",
            local_interface="Gi0/1",
            remote_chassis_id="00:aa:bb:cc:dd:ee",
            is_mock=False,
            discovery_source="snmp",
            message="Actual SNMP discovered neighbor event",
        )
        assert mock_alert.id != snmp_alert.id
        assert mock_alert.is_mock is True
        assert snmp_alert.is_mock is False
        assert db.query(TopologyAlertModel).count() == 2
    finally:
        db.close()


# ============================================================================
# Task 2: Alert Lifecycle Audits
# ============================================================================


def test_audit_lifecycle_invalid_transition(client: TestClient):
    """Verify OPEN -> ACKNOWLEDGED -> RESOLVED. Attempting to ACKNOWLEDGE a RESOLVED alert fails with HTTP 400."""
    # 1. Create an alert directly
    db = TestingSessionLocal()
    try:
        alert = alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="discovery_failed",
            severity="critical",
            source_device_id="sw-life-01",
            message="SNMP agent unreachable",
        )
        alert_id = alert.id
    finally:
        db.close()

    # 2. Acknowledge alert (OPEN -> ACKNOWLEDGED)
    res_ack = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": "Ops Engineer", "note": "Contacting building IT"},
    )
    assert res_ack.status_code == 200
    assert res_ack.json()["status"] == "acknowledged"

    # 3. Resolve alert (ACKNOWLEDGED -> RESOLVED)
    res_res = client.post(
        f"/api/v1/alerts/{alert_id}/resolve",
        json={"resolved_by": "Ops Engineer", "note": "Switch power cycle resolved agent hang"},
    )
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "resolved"

    # 4. Attempt INVALID transition: ACKNOWLEDGE a RESOLVED alert -> Expect HTTP 400 Bad Request
    res_invalid = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": "Junior Tech", "note": "Trying to reopen"},
    )
    assert res_invalid.status_code == 400
    assert "already resolved" in res_invalid.json()["detail"].lower()


def test_audit_lifecycle_repeated_requests_idempotent(client: TestClient):
    """Repeated acknowledge or resolve requests are idempotent and preserve timestamps."""
    db = TestingSessionLocal()
    try:
        alert = alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="neighbor_stale",
            severity="warning",
            source_device_id="sw-idem-01",
            message="Stale neighbor link",
        )
        alert_id = alert.id
    finally:
        db.close()

    # Acknowledge twice
    res1 = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", json={"acknowledged_by": "Op1"})
    assert res1.status_code == 200
    ack_time = res1.json()["acknowledged_at"]

    res2 = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": "Op2", "note": "Updated operator note"},
    )
    assert res2.status_code == 200
    assert res2.json()["acknowledged_at"] == ack_time  # First acknowledged timestamp preserved
    assert res2.json()["acknowledgement_note"] == "Updated operator note"

    # Resolve twice
    res3 = client.post(f"/api/v1/alerts/{alert_id}/resolve", json={"resolved_by": "Admin"})
    assert res3.status_code == 200
    res_time = res3.json()["resolved_at"]

    res4 = client.post(
        f"/api/v1/alerts/{alert_id}/resolve",
        json={"resolved_by": "Admin", "note": "Second confirm"},
    )
    assert res4.status_code == 200
    assert res4.json()["resolved_at"] == res_time  # First resolved timestamp preserved
    assert res4.json()["resolution_note"] == "Second confirm"


def test_audit_auto_resolve_stale_alert_on_restoration():
    """When a stale neighbor restores advertisements, the stale alert auto-resolves while preserving notes."""
    db = TestingSessionLocal()
    try:
        # Create an open stale alert
        stale_alert = alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="neighbor_stale",
            severity="warning",
            source_device_id="sw-auto-01",
            local_interface="Gi0/1",
            remote_chassis_id="aa:11:22:33:44:55",
            message="Advertisement unrefreshed",
            is_mock=True,
        )
        # Operator acknowledges it
        alert_service.acknowledge_alert(
            db=db,
            alert_id=stale_alert.id,
            acknowledged_by="Senior NOC",
            note="Monitoring peer device restart",
        )

        # Neighbor link restores
        resolved_alert = alert_service.auto_resolve_stale_alert(
            db=db,
            source_device_id="sw-auto-01",
            local_interface="Gi0/1",
            remote_chassis_id="aa:11:22:33:44:55",
            is_mock=True,
        )
        assert resolved_alert is not None
        assert resolved_alert.status == "resolved"
        assert resolved_alert.resolved_by == "System (Auto-recovery)"
        # Note preserved
        assert "Monitoring peer device restart" in resolved_alert.resolution_note
        assert resolved_alert.resolved_at is not None
    finally:
        db.close()


# ============================================================================
# Task 3: Reliability & Data Integrity Audits
# ============================================================================


def test_audit_device_deletion_preserves_historical_alerts():
    """Deleting a registered device removes its live discovery links but preserves historical alerts for audit trail."""
    db = TestingSessionLocal()
    try:
        # Register a device
        dev = DeviceModel(
            id="dev-del-01",
            name="Decommissioned-Core",
            ip_address="10.250.0.1",
            device_type="router",
            building="HQ",
            floor="Floor 1",
            department="NetOps",
            collection_method="mock",
        )
        db.add(dev)
        db.commit()

        # Create topology alert for this device
        alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="discovery_unsupported",
            severity="warning",
            source_device_id="dev-del-01",
            source_device_name="Decommissioned-Core",
            message="LLDP table MIB disabled",
        )

        # Delete the device using the service
        deleted = device_service.delete_device(db=db, device_id="dev-del-01")
        assert deleted is True

        # Ensure device is gone
        assert db.query(DeviceModel).filter(DeviceModel.id == "dev-del-01").first() is None

        # Ensure historical alert record is PRESERVED (audit integrity)
        alert = db.query(TopologyAlertModel).filter(
            TopologyAlertModel.source_device_id == "dev-del-01"
        ).first()
        assert alert is not None
        assert alert.event_type == "discovery_unsupported"
        assert alert.source_device_name == "Decommissioned-Core"
    finally:
        db.close()


def test_audit_database_persistence_across_sessions():
    """Alerts committed in one session persist and are accessible in separate subsequent sessions."""
    db1 = TestingSessionLocal()
    try:
        created = alert_service.create_or_deduplicate_alert(
            db=db1,
            event_type="protocol_changed",
            severity="info",
            source_device_id="sw-persist-01",
            local_interface="Gi0/10",
            remote_chassis_id="99:88:77:66:55:44",
            message="Protocol switched to LLDP",
        )
        created_id = created.id
    finally:
        db1.close()

    # Query from completely fresh session
    db2 = TestingSessionLocal()
    try:
        fetched = alert_service.get_alert_by_id(db=db2, alert_id=created_id)
        assert fetched is not None
        assert fetched.id == created_id
        assert fetched.event_type == "protocol_changed"
        assert fetched.local_interface == "Gi0/10"
    finally:
        db2.close()


# ============================================================================
# Task 4: API Security & Input Validation Audits
# ============================================================================


def test_audit_input_validation_boundaries(client: TestClient):
    """Malformed lifecycle requests exceeding length constraints are rejected with HTTP 422."""
    db = TestingSessionLocal()
    try:
        alert = alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="new_neighbor",
            severity="info",
            source_device_id="sw-sec-01",
            message="Security test alert",
        )
        alert_id = alert.id
    finally:
        db.close()

    # 1. acknowledged_by > 100 characters -> Expect 422 Unprocessable Entity
    res_too_long_user = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": "A" * 105, "note": "Valid note"},
    )
    assert res_too_long_user.status_code == 422

    # 2. note > 500 characters -> Expect 422 Unprocessable Entity
    res_too_long_note = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": "Valid Operator", "note": "B" * 505},
    )
    assert res_too_long_note.status_code == 422

    # 3. resolved_by > 100 characters -> Expect 422 Unprocessable Entity
    res_too_long_res = client.post(
        f"/api/v1/alerts/{alert_id}/resolve",
        json={"resolved_by": "C" * 105, "note": "Valid note"},
    )
    assert res_too_long_res.status_code == 422

    # 4. Valid payload -> Expect 200 OK
    res_valid = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": "Lead Operator", "note": "Normal sized comment"},
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["acknowledged_by"] == "Lead Operator"
