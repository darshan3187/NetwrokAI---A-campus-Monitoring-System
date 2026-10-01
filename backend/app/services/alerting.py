"""Topology Change Detection & Alerting Service (Phase 6).

Detects layer-2 topology changes between successive LLDP/CDP discovery cycles:
- New neighbor observed
- Neighbor observation became stale (unrefreshed advertisement window)
- Stale neighbor restored to active
- Neighbor interface mapping changed
- Discovery protocol switched (LLDP <-> CDP)
- Discovery operation failed or unsupported

Enforces alert deduplication without spamming or mutating historical discovery records.
"""

from datetime import datetime, timezone
from dataclasses import dataclass
import json
import logging
import threading
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import DeviceModel, TopologyAlertModel, TopologyLinkModel

logger = logging.getLogger("network_monitoring.alerts")


@dataclass
class PreviousLinkSnapshot:
    """Immutable snapshot of a topology link prior to running a new discovery cycle."""

    local_interface: str
    remote_chassis_id: str
    remote_port_id: str
    protocol: str
    link_status: str
    remote_device_id: Optional[str] = None
    remote_system_name: Optional[str] = None


class TopologyAlertService:
    """Manages topology change detection events, deduplication, and alert lifecycle."""

    def __init__(self):
        self._lock = threading.Lock()

    def create_or_deduplicate_alert(
        self,
        db: Session,
        event_type: str,
        severity: str,
        source_device_id: str,
        source_device_name: Optional[str] = None,
        remote_device_id: Optional[str] = None,
        remote_device_name: Optional[str] = None,
        remote_chassis_id: Optional[str] = None,
        local_interface: Optional[str] = None,
        remote_port_id: Optional[str] = None,
        protocol: Optional[str] = None,
        message: str = "",
        details: Optional[Dict[str, Any]] = None,
        is_mock: bool = False,
        discovery_source: str = "snmp",
    ) -> TopologyAlertModel:
        """Create a new alert or deduplicate against existing active (open/acknowledged) alerts."""
        with self._lock:
            now = datetime.now(timezone.utc)

            # Build query for deduplication of active conditions
            query = db.query(TopologyAlertModel).filter(
                TopologyAlertModel.source_device_id == source_device_id,
                TopologyAlertModel.event_type == event_type,
                TopologyAlertModel.status.in_(["open", "acknowledged"]),
                TopologyAlertModel.is_mock == is_mock,
            )

            if local_interface is not None:
                query = query.filter(TopologyAlertModel.local_interface == local_interface)
            else:
                query = query.filter(TopologyAlertModel.local_interface.is_(None))

            if remote_chassis_id is not None:
                query = query.filter(TopologyAlertModel.remote_chassis_id == remote_chassis_id)
            else:
                query = query.filter(TopologyAlertModel.remote_chassis_id.is_(None))

            existing_alert = query.first()

            details_json = json.dumps(details) if details else None

            if existing_alert:
                # Deduplicate: update last_seen_at and increment count
                existing_alert.last_seen_at = now
                existing_alert.occurrence_count += 1
                existing_alert.message = message
                if details_json:
                    existing_alert.details = details_json
                if source_device_name and not existing_alert.source_device_name:
                    existing_alert.source_device_name = source_device_name
                if remote_device_name and not existing_alert.remote_device_name:
                    existing_alert.remote_device_name = remote_device_name
                db.commit()
                db.refresh(existing_alert)
                logger.debug(
                    "Deduplicated alert %s for %s (%s, count=%d)",
                    existing_alert.id,
                    source_device_id,
                    event_type,
                    existing_alert.occurrence_count,
                )
                return existing_alert

            # Create fresh alert record
            alert_id = f"alert_{uuid.uuid4().hex[:12]}"
            new_alert = TopologyAlertModel(
                id=alert_id,
                event_type=event_type,
                severity=severity,
                status="open",
                source_device_id=source_device_id,
                source_device_name=source_device_name,
                remote_device_id=remote_device_id,
                remote_device_name=remote_device_name,
                remote_chassis_id=remote_chassis_id,
                local_interface=local_interface,
                remote_port_id=remote_port_id,
                protocol=protocol,
                message=message,
                details=details_json,
                first_detected_at=now,
                last_seen_at=now,
                occurrence_count=1,
                is_mock=is_mock,
                discovery_source=discovery_source,
            )

            db.add(new_alert)
            db.commit()
            db.refresh(new_alert)
            logger.info(
                "Created new topology alert %s: [%s] %s on %s",
                alert_id,
                severity.upper(),
                event_type,
                source_device_id,
            )
            return new_alert

    def process_discovery_events(
        self,
        db: Session,
        device: DeviceModel,
        result: Any,  # DiscoveryResult
        previous_links: List[TopologyLinkModel],
        current_links: List[TopologyLinkModel],
    ) -> List[TopologyAlertModel]:
        """Evaluate differences between previous and current discovery cycles and trigger alerts."""
        alerts_generated: List[TopologyAlertModel] = []
        is_mock = device.collection_method == "mock"
        source_name = device.name

        # Case 1: Discovery Failed
        if not result.success and result.status == "failed":
            alert = self.create_or_deduplicate_alert(
                db=db,
                event_type="discovery_failed",
                severity="critical",
                source_device_id=device.id,
                source_device_name=source_name,
                message=f"Topology discovery failed for {source_name} ({device.ip_address}): {result.error_message or 'SNMP connection error'}",
                details={"error": result.error_message, "ip": device.ip_address},
                is_mock=is_mock,
                discovery_source="mock" if is_mock else "snmp",
            )
            alerts_generated.append(alert)
            return alerts_generated

        # Case 2: Discovery Unsupported
        if result.status == "unsupported":
            alert = self.create_or_deduplicate_alert(
                db=db,
                event_type="discovery_unsupported",
                severity="warning",
                source_device_id=device.id,
                source_device_name=source_name,
                message=f"Discovery unsupported on {source_name}: LLDP and CDP MIB tables are not enabled or supported on this device.",
                details={"message": result.error_message},
                is_mock=is_mock,
                discovery_source="mock" if is_mock else "snmp",
            )
            alerts_generated.append(alert)
            return alerts_generated

        # Compare links across discovery cycles
        prev_by_key: Dict[tuple, TopologyLinkModel] = {
            (l.local_interface.strip().lower(), l.remote_chassis_id.strip().lower()): l
            for l in previous_links
        }
        prev_by_chassis: Dict[str, TopologyLinkModel] = {
            l.remote_chassis_id.strip().lower(): l for l in previous_links
        }

        for curr in current_links:
            local_key = curr.local_interface.strip().lower()
            chassis_key = curr.remote_chassis_id.strip().lower()
            key = (local_key, chassis_key)

            prev = prev_by_key.get(key)
            remote_label = curr.remote_system_name or curr.remote_device_id or curr.remote_chassis_id

            if prev is None:
                # Check if this chassis ID was previously seen on a DIFFERENT interface
                prev_chassis = prev_by_chassis.get(chassis_key)
                if prev_chassis and prev_chassis.local_interface.strip().lower() != local_key:
                    # Interface changed
                    alert = self.create_or_deduplicate_alert(
                        db=db,
                        event_type="interface_changed",
                        severity="warning",
                        source_device_id=device.id,
                        source_device_name=source_name,
                        remote_device_id=curr.remote_device_id,
                        remote_device_name=curr.remote_system_name,
                        remote_chassis_id=curr.remote_chassis_id,
                        local_interface=curr.local_interface,
                        remote_port_id=curr.remote_port_id,
                        protocol=curr.protocol,
                        message=f"Neighbor {remote_label} shifted interface on {source_name} from {prev_chassis.local_interface} to {curr.local_interface}.",
                        details={
                            "previous_interface": prev_chassis.local_interface,
                            "new_interface": curr.local_interface,
                            "remote_port": curr.remote_port_id,
                        },
                        is_mock=(curr.discovery_source == "mock"),
                        discovery_source=curr.discovery_source,
                    )
                    alerts_generated.append(alert)
                else:
                    # New neighbor observed
                    alert = self.create_or_deduplicate_alert(
                        db=db,
                        event_type="new_neighbor",
                        severity="info",
                        source_device_id=device.id,
                        source_device_name=source_name,
                        remote_device_id=curr.remote_device_id,
                        remote_device_name=curr.remote_system_name,
                        remote_chassis_id=curr.remote_chassis_id,
                        local_interface=curr.local_interface,
                        remote_port_id=curr.remote_port_id,
                        protocol=curr.protocol,
                        message=f"New {curr.protocol.upper()} neighbor observed on {source_name} ({curr.local_interface}) -> {remote_label} ({curr.remote_port_id}).",
                        details={
                            "protocol": curr.protocol,
                            "resolution_state": curr.resolution_state,
                            "remote_port_desc": curr.remote_port_desc,
                        },
                        is_mock=(curr.discovery_source == "mock"),
                        discovery_source=curr.discovery_source,
                    )
                    alerts_generated.append(alert)
            else:
                # Existing neighbor: check if previously stale and now restored
                if prev.link_status == "stale" and curr.link_status == "active":
                    alert = self.create_or_deduplicate_alert(
                        db=db,
                        event_type="neighbor_restored",
                        severity="info",
                        source_device_id=device.id,
                        source_device_name=source_name,
                        remote_device_id=curr.remote_device_id,
                        remote_device_name=curr.remote_system_name,
                        remote_chassis_id=curr.remote_chassis_id,
                        local_interface=curr.local_interface,
                        remote_port_id=curr.remote_port_id,
                        protocol=curr.protocol,
                        message=f"Neighbor {remote_label} on {source_name} ({curr.local_interface}) renewed advertisements and returned to active state.",
                        details={"restored_at": curr.last_seen_at.isoformat() if curr.last_seen_at else None},
                        is_mock=(curr.discovery_source == "mock"),
                        discovery_source=curr.discovery_source,
                    )
                    alerts_generated.append(alert)

                    # Auto-resolve any active neighbor_stale alert for this restored link
                    self.auto_resolve_stale_alert(
                        db=db,
                        source_device_id=device.id,
                        local_interface=curr.local_interface,
                        remote_chassis_id=curr.remote_chassis_id,
                        is_mock=(curr.discovery_source == "mock"),
                    )

                # Check if protocol observation changed (e.g. LLDP -> CDP)
                if prev.protocol != curr.protocol:
                    alert = self.create_or_deduplicate_alert(
                        db=db,
                        event_type="protocol_changed",
                        severity="info",
                        source_device_id=device.id,
                        source_device_name=source_name,
                        remote_device_id=curr.remote_device_id,
                        remote_device_name=curr.remote_system_name,
                        remote_chassis_id=curr.remote_chassis_id,
                        local_interface=curr.local_interface,
                        remote_port_id=curr.remote_port_id,
                        protocol=curr.protocol,
                        message=f"Neighbor advertisement protocol for {remote_label} on {source_name} changed from {prev.protocol.upper()} to {curr.protocol.upper()}.",
                        details={"old_protocol": prev.protocol, "new_protocol": curr.protocol},
                        is_mock=(curr.discovery_source == "mock"),
                        discovery_source=curr.discovery_source,
                    )
                    alerts_generated.append(alert)

        return alerts_generated

    def process_stale_events(
        self,
        db: Session,
        staled_links: List[TopologyLinkModel],
    ) -> List[TopologyAlertModel]:
        """Generate stale observation warnings for links that exceeded the freshness window."""
        alerts: List[TopologyAlertModel] = []
        for link in staled_links:
            remote_label = link.remote_system_name or link.remote_device_id or link.remote_chassis_id
            alert = self.create_or_deduplicate_alert(
                db=db,
                event_type="neighbor_stale",
                severity="warning",
                source_device_id=link.source_device_id,
                remote_device_id=link.remote_device_id,
                remote_device_name=link.remote_system_name,
                remote_chassis_id=link.remote_chassis_id,
                local_interface=link.local_interface,
                remote_port_id=link.remote_port_id,
                protocol=link.protocol,
                message=f"Neighbor observation on {link.source_device_id} ({link.local_interface}) -> {remote_label} exceeded freshness window without renewal (unrefreshed advertisement, not confirmed line failure).",
                details={
                    "last_seen_at": link.last_seen_at.isoformat() if link.last_seen_at else None,
                    "protocol": link.protocol,
                },
                is_mock=(link.discovery_source == "mock"),
                discovery_source=link.discovery_source,
            )
            alerts.append(alert)
        return alerts

    def get_alerts(
        self,
        db: Session,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        event_type: Optional[str] = None,
        device_id: Optional[str] = None,
        is_mock: Optional[bool] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TopologyAlertModel]:
        """Fetch filtered alerts ordered by most recent observation."""
        query = db.query(TopologyAlertModel)

        if status and status.lower() != "all":
            query = query.filter(TopologyAlertModel.status == status.lower())
        if severity and severity.lower() != "all":
            query = query.filter(TopologyAlertModel.severity == severity.lower())
        if event_type and event_type.lower() != "all":
            query = query.filter(TopologyAlertModel.event_type == event_type.lower())
        if device_id:
            query = query.filter(
                or_(
                    TopologyAlertModel.source_device_id == device_id,
                    TopologyAlertModel.remote_device_id == device_id,
                )
            )
        if is_mock is not None:
            query = query.filter(TopologyAlertModel.is_mock == is_mock)
        if start_time:
            query = query.filter(TopologyAlertModel.last_seen_at >= start_time)
        if end_time:
            query = query.filter(TopologyAlertModel.last_seen_at <= end_time)

        return (
            query.order_by(TopologyAlertModel.last_seen_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_alert_by_id(self, db: Session, alert_id: str) -> Optional[TopologyAlertModel]:
        """Fetch a specific alert by its unique identifier."""
        return db.query(TopologyAlertModel).filter(TopologyAlertModel.id == alert_id).first()

    def get_alert_summary(self, db: Session) -> Dict[str, Any]:
        """Aggregate total counts by status, severity, and event type."""
        all_alerts = db.query(TopologyAlertModel).all()

        total = len(all_alerts)
        open_count = sum(1 for a in all_alerts if a.status == "open")
        ack_count = sum(1 for a in all_alerts if a.status == "acknowledged")
        resolved_count = sum(1 for a in all_alerts if a.status == "resolved")

        by_severity: Dict[str, int] = {}
        by_event_type: Dict[str, int] = {}
        mock_count = 0
        actual_count = 0

        for a in all_alerts:
            by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
            by_event_type[a.event_type] = by_event_type.get(a.event_type, 0) + 1
            if a.is_mock:
                mock_count += 1
            else:
                actual_count += 1

        return {
            "total_alerts": total,
            "open_alerts": open_count,
            "acknowledged_alerts": ack_count,
            "resolved_alerts": resolved_count,
            "by_severity": by_severity,
            "by_event_type": by_event_type,
            "mock_alerts_count": mock_count,
            "actual_alerts_count": actual_count,
            "timestamp": datetime.now(timezone.utc),
        }

    def auto_resolve_stale_alert(
        self,
        db: Session,
        source_device_id: str,
        local_interface: Optional[str],
        remote_chassis_id: Optional[str],
        is_mock: bool = False,
    ) -> Optional[TopologyAlertModel]:
        """Auto-resolve any active (open or acknowledged) stale neighbor alert upon link restoration."""
        with self._lock:
            query = db.query(TopologyAlertModel).filter(
                TopologyAlertModel.source_device_id == source_device_id,
                TopologyAlertModel.event_type == "neighbor_stale",
                TopologyAlertModel.status.in_(["open", "acknowledged"]),
                TopologyAlertModel.is_mock == is_mock,
            )
            if local_interface is not None:
                query = query.filter(TopologyAlertModel.local_interface == local_interface)
            else:
                query = query.filter(TopologyAlertModel.local_interface.is_(None))

            if remote_chassis_id is not None:
                query = query.filter(TopologyAlertModel.remote_chassis_id == remote_chassis_id)
            else:
                query = query.filter(TopologyAlertModel.remote_chassis_id.is_(None))

            stale_alert = query.first()
            if stale_alert:
                now = datetime.now(timezone.utc)
                stale_alert.status = "resolved"
                stale_alert.resolved_at = now
                stale_alert.resolved_by = "System (Auto-recovery)"
                res_note = "Auto-resolved: Neighbor advertisements renewed and returned to active state."
                if stale_alert.acknowledgement_note:
                    stale_alert.resolution_note = f"{res_note} (Prior note: {stale_alert.acknowledgement_note})"
                else:
                    stale_alert.resolution_note = res_note
                db.commit()
                db.refresh(stale_alert)
                logger.info(
                    "Auto-resolved stale alert %s for %s (%s)",
                    stale_alert.id,
                    source_device_id,
                    local_interface,
                )
                return stale_alert
            return None

    def acknowledge_alert(
        self,
        db: Session,
        alert_id: str,
        acknowledged_by: str = "Network Operator",
        note: Optional[str] = None,
    ) -> Optional[TopologyAlertModel]:
        """Transition an alert from open to acknowledged. Rejects already resolved alerts."""
        with self._lock:
            alert = self.get_alert_by_id(db, alert_id)
            if not alert:
                return None

            if alert.status == "resolved":
                raise ValueError(
                    f"Cannot acknowledge alert '{alert_id}': Alert is already resolved. "
                    "Only open or acknowledged alerts may be acknowledged."
                )

            alert.status = "acknowledged"
            if not alert.acknowledged_at:
                alert.acknowledged_at = datetime.now(timezone.utc)
            alert.acknowledged_by = acknowledged_by
            if note:
                alert.acknowledgement_note = note
            db.commit()
            db.refresh(alert)
            logger.info("Alert %s acknowledged by %s", alert_id, acknowledged_by)
            return alert

    def resolve_alert(
        self,
        db: Session,
        alert_id: str,
        resolved_by: str = "Network Operator",
        note: Optional[str] = None,
    ) -> Optional[TopologyAlertModel]:
        """Transition an alert to resolved. Idempotent if already resolved."""
        with self._lock:
            alert = self.get_alert_by_id(db, alert_id)
            if not alert:
                return None

            alert.status = "resolved"
            if not alert.resolved_at:
                alert.resolved_at = datetime.now(timezone.utc)
            alert.resolved_by = resolved_by
            if note:
                alert.resolution_note = note
            db.commit()
            db.refresh(alert)
            logger.info("Alert %s resolved by %s", alert_id, resolved_by)
            return alert


# Global singleton alert service instance
alert_service = TopologyAlertService()
