"""Seed script for Phase 7: College Demonstration Scenario.

Initializes a reproducible, deterministic demo state using mock devices only:
- 4 mock campus devices across departments
- Topology discovery with resolved and unresolved neighbors
- Alert history with open, acknowledged, and auto-resolved records
- Clearly marked as SIMULATED / MOCK data throughout the system.
"""

from datetime import datetime, timezone
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, init_db
from app.models import DeviceModel, TopologyAlertModel, TopologyLinkModel, TopologyDiscoveryStatusModel
from app.services.alerting import alert_service
from app.services.topology import topology_service, DiscoveredNeighbor


DEMO_DEVICE_IDS = ["demo-core-01", "demo-dist-01", "demo-edge-01", "demo-gw-01"]


def seed_demo():
    """Seeds deterministic demo data safely without affecting real devices or telemetry."""
    print("[*] Initializing Database for Phase 7 Demo Scenario...")
    init_db()
    db = SessionLocal()

    try:
        # 1. Clean previous demo records if existing (strictly scoped to DEMO_DEVICE_IDS)
        # Guarantees idempotence: running multiple times never duplicates rows
        # Guarantees safety: real devices, local psutil metrics, and real SNMP telemetry remain untouched
        print("[*] Purging previous demo records (scoped strictly to demo-* identifiers)...")
        db.query(TopologyAlertModel).filter(
            TopologyAlertModel.source_device_id.in_(DEMO_DEVICE_IDS) | TopologyAlertModel.remote_device_id.in_(DEMO_DEVICE_IDS)
        ).delete(synchronize_session=False)
        db.query(TopologyLinkModel).filter(
            TopologyLinkModel.source_device_id.in_(DEMO_DEVICE_IDS) | TopologyLinkModel.remote_device_id.in_(DEMO_DEVICE_IDS)
        ).delete(synchronize_session=False)
        db.query(TopologyDiscoveryStatusModel).filter(
            TopologyDiscoveryStatusModel.device_id.in_(DEMO_DEVICE_IDS)
        ).delete(synchronize_session=False)
        db.query(DeviceModel).filter(DeviceModel.id.in_(DEMO_DEVICE_IDS)).delete(synchronize_session=False)
        db.commit()

        # 2. Register Four Mock Campus Devices
        print("[*] Registering 4 Mock Devices...")
        devices = [
            DeviceModel(
                id="demo-core-01",
                name="Campus-Core-Switch",
                ip_address="10.0.1.1",
                device_type="switch",
                building="Main Administration",
                floor="Floor 1",
                department="IT Operations",
                collection_method="mock",
                vendor_model="Cisco Catalyst 9500",
                connection_status="online",
                monitoring_status="active",
                reachability="reachable",
            ),
            DeviceModel(
                id="demo-dist-01",
                name="Science-Dist-Switch",
                ip_address="10.0.2.1",
                device_type="switch",
                building="Science Hall",
                floor="Floor 2",
                department="Physics",
                collection_method="mock",
                vendor_model="Cisco Catalyst 9300",
                connection_status="online",
                monitoring_status="active",
                reachability="reachable",
            ),
            DeviceModel(
                id="demo-edge-01",
                name="Engineering-Edge-Switch",
                ip_address="10.0.3.1",
                device_type="switch",
                building="Engineering Block",
                floor="Floor 1",
                department="ECE",
                collection_method="mock",
                vendor_model="Aruba CX 6300",
                connection_status="online",
                monitoring_status="active",
                reachability="reachable",
            ),
            DeviceModel(
                id="demo-gw-01",
                name="Campus-Gateway-Router",
                ip_address="10.0.0.1",
                device_type="router",
                building="Data Center",
                floor="Basement",
                department="IT Operations",
                collection_method="mock",
                vendor_model="Cisco ISR 4451",
                connection_status="online",
                monitoring_status="active",
                reachability="reachable",
            ),
        ]
        for dev in devices:
            db.add(dev)
        db.commit()

        # 3. Configure and trigger discovery on demo-core-01
        print("[*] Generating Topology Links for demo-core-01...")
        topology_service.mock_provider._mock_topologies["demo-core-01"] = [
            DiscoveredNeighbor(
                local_interface="GigabitEthernet0/1",
                remote_chassis_id="00:1A:2B:CC:DD:01",
                remote_chassis_id_subtype="mac_address",
                remote_port_id="GigabitEthernet0/24",
                remote_port_id_subtype="interface_name",
                remote_port_desc="Trunk to Science Hall Dist",
                remote_system_name="Science-Dist-Switch",
                remote_system_desc="Cisco Catalyst 9300",
                protocol="cdp",
                discovery_source="mock",
                raw_address="10.0.2.1",
            ),
            DiscoveredNeighbor(
                local_interface="GigabitEthernet0/2",
                remote_chassis_id="00:1A:2B:EE:FF:02",
                remote_chassis_id_subtype="mac_address",
                remote_port_id="GigabitEthernet0/24",
                remote_port_id_subtype="interface_name",
                remote_port_desc="Trunk to Engineering Edge",
                remote_system_name="Engineering-Edge-Switch",
                remote_system_desc="Aruba CX 6300",
                protocol="lldp",
                discovery_source="mock",
                raw_address="10.0.3.1",
            ),
            DiscoveredNeighbor(
                local_interface="GigabitEthernet0/3",
                remote_chassis_id="00:50:56:AA:BB:CC",
                remote_chassis_id_subtype="mac_address",
                remote_port_id="eth0",
                remote_port_id_subtype="interface_name",
                remote_port_desc="Lab Department Access Point",
                remote_system_name="unregistered-guest-ap",
                remote_system_desc="Aruba Instant On AP22",
                protocol="lldp",
                discovery_source="mock",
                raw_address="192.168.99.200",
            ),
        ]

        res = topology_service.discover_device(db=db, device_id="demo-core-01")
        print(f"[*] Discovery executed: {len(res.neighbors)} neighbors ({res.resolved_neighbors_count} resolved)")

        # 4. Acknowledge the Unmanaged AP alert
        print("[*] Creating Demo Alert Lifecycle History...")
        ap_alert = db.query(TopologyAlertModel).filter(
            TopologyAlertModel.source_device_id == "demo-core-01",
            TopologyAlertModel.local_interface == "GigabitEthernet0/3",
            TopologyAlertModel.event_type == "new_neighbor",
        ).first()
        if ap_alert:
            alert_service.acknowledge_alert(
                db=db,
                alert_id=ap_alert.id,
                acknowledged_by="Lead Network Admin",
                note="Verified authorized guest access point in Student Hall",
            )
            print(f"[*] Acknowledged Alert {ap_alert.id}")

        # 5. Create a historical auto-resolved stale alert
        stale_alert = alert_service.create_or_deduplicate_alert(
            db=db,
            event_type="neighbor_stale",
            severity="warning",
            source_device_id="demo-core-01",
            source_device_name="Campus-Core-Switch",
            remote_device_id="demo-dist-01",
            remote_device_name="Science-Dist-Switch",
            remote_chassis_id="00:1A:2B:CC:DD:01",
            local_interface="GigabitEthernet0/1",
            remote_port_id="GigabitEthernet0/24",
            protocol="cdp",
            message="Neighbor observation on demo-core-01 (GigabitEthernet0/1) -> Science-Dist-Switch exceeded freshness window without renewal (unrefreshed advertisement, not confirmed line failure).",
            is_mock=True,
            discovery_source="mock",
        )
        alert_service.resolve_alert(
            db=db,
            alert_id=stale_alert.id,
            resolved_by="System (Auto-recovery)",
            note="Auto-resolved: Neighbor renewed advertisements on GigabitEthernet0/1 and returned to active state.",
        )
        print(f"[*] Auto-resolved Alert {stale_alert.id} recorded in history.")

        # Summary count
        demo_dev_count = db.query(DeviceModel).filter(DeviceModel.id.in_(DEMO_DEVICE_IDS)).count()
        open_c = db.query(TopologyAlertModel).filter(TopologyAlertModel.status == "open").count()
        ack_c = db.query(TopologyAlertModel).filter(TopologyAlertModel.status == "acknowledged").count()
        res_c = db.query(TopologyAlertModel).filter(TopologyAlertModel.status == "resolved").count()
        print(f"[SUCCESS] Demo scenario seeded successfully!")
        print(f"          Demo Devices: {demo_dev_count} | Open Alerts: {open_c} | Acknowledged: {ack_c} | Resolved: {res_c}")

    except Exception as exc:
        db.rollback()
        print(f"[ERROR] Seeding failed: {exc}. Database transaction safely rolled back.", file=sys.stderr)
        raise
    finally:
        db.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="NetworkAI College Demo Scenario Seeder (Safe & Idempotent)",
        epilog="""
Startup & Usage Instructions:
  1. Ensure your backend virtual environment is active.
  2. Run: python seed_demo_scenario.py
  3. Start the FastAPI backend: uvicorn app.main:app --reload --port 8000
  4. Start the frontend: cd ../frontend && npm run dev
  5. Open http://localhost:5173 to view the seeded demo environment.

Safety Guarantees:
  - Scoped strictly to demo device IDs (demo-core-01, demo-dist-01, demo-edge-01, demo-gw-01).
  - Never touches or overwrites real registered devices, local psutil metrics, or SNMP telemetry.
  - Safe to run multiple times: existing demo records are idempotently purged before re-seeding.
  - On error, transactions are automatically rolled back.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.parse_args()
    seed_demo()


if __name__ == "__main__":
    main()
