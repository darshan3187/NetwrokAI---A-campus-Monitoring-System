"""Service layer for multi-device campus network registry (Phase 1).

Provides device inventory persistence, unique constraint enforcement,
query filtering, partial updates, and statistical aggregations without
triggering remote network polling or storing sensitive credentials.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import (
    DeviceModel,
    DeviceTelemetryModel,
    TopologyDiscoveryStatusModel,
    TopologyLinkModel,
)
from app.schemas import (
    CampusBuildingNode,
    CampusDepartmentNode,
    CampusDeviceNode,
    CampusFloorNode,
    CampusHierarchyResponse,
    CampusTelemetrySummaryResponse,
    CampusTimelinePoint,
    CampusTimelineResponse,
    DeviceComparisonItem,
    DeviceComparisonResponse,
    DeviceCreateRequest,
    DeviceSummaryResponse,
    DeviceUpdateRequest,
)

logger = logging.getLogger("network_monitoring.devices")


class DeviceRegistryService:
    """Manages CRUD operations and statistics for campus network devices."""

    def create_device(self, db: Session, req: DeviceCreateRequest) -> DeviceModel:
        """Create a new campus device in the registry with uniqueness checks.

        Ensures management IP address and device ID are unique across all records.
        """
        device_id = req.id.strip() if req.id else f"dev-{uuid.uuid4().hex[:8]}"

        # Check ID collision
        existing_id = db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
        if existing_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Device with ID '{device_id}' already exists.",
            )

        # Check IP collision
        clean_ip = req.ip_address.strip()
        existing_ip = db.query(DeviceModel).filter(DeviceModel.ip_address == clean_ip).first()
        if existing_ip:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Device with IP address '{clean_ip}' is already registered (device '{existing_ip.name}').",
            )

        now = datetime.now(timezone.utc)
        device = DeviceModel(
            id=device_id,
            name=req.name.strip(),
            ip_address=clean_ip,
            device_type=req.device_type.strip().lower(),
            building=req.building.strip(),
            department=req.department.strip(),
            floor=req.floor.strip(),
            location_description=req.location_description.strip() if req.location_description else None,
            vendor_model=req.vendor_model.strip() if req.vendor_model else None,
            collection_method=req.collection_method.strip().lower(),
            monitoring_status=req.monitoring_status.strip().lower(),
            connection_status=req.connection_status.strip().lower(),
            created_at=now,
            updated_at=now,
        )

        db.add(device)
        db.commit()
        db.refresh(device)
        logger.info("Registered new device '%s' (%s) with ID %s", device.name, device.ip_address, device.id)
        return device

    def get_device(self, db: Session, device_id: str) -> Optional[DeviceModel]:
        """Fetch a single device by ID."""
        return db.query(DeviceModel).filter(DeviceModel.id == device_id).first()

    def list_devices(
        self,
        db: Session,
        device_type: Optional[str] = None,
        department: Optional[str] = None,
        building: Optional[str] = None,
        floor: Optional[str] = None,
        monitoring_status: Optional[str] = None,
        connection_status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[DeviceModel]:
        """Retrieve registered devices filtered by criteria and search query."""
        query = db.query(DeviceModel)

        if device_type:
            query = query.filter(DeviceModel.device_type == device_type.strip().lower())
        if department:
            query = query.filter(DeviceModel.department == department.strip())
        if building:
            query = query.filter(DeviceModel.building == building.strip())
        if floor:
            query = query.filter(DeviceModel.floor == floor.strip())
        if monitoring_status:
            query = query.filter(DeviceModel.monitoring_status == monitoring_status.strip().lower())
        if connection_status:
            query = query.filter(DeviceModel.connection_status == connection_status.strip().lower())

        if search:
            s = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    DeviceModel.name.ilike(s),
                    DeviceModel.ip_address.ilike(s),
                    DeviceModel.building.ilike(s),
                    DeviceModel.department.ilike(s),
                    DeviceModel.vendor_model.ilike(s),
                    DeviceModel.location_description.ilike(s),
                    DeviceModel.id.ilike(s),
                )
            )

        return query.order_by(DeviceModel.created_at.desc()).all()

    def update_device(
        self,
        db: Session,
        device_id: str,
        req: DeviceUpdateRequest,
    ) -> Optional[DeviceModel]:
        """Partially update fields of an existing device record."""
        device = db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
        if not device:
            return None

        # Check IP collision if IP is being modified
        if req.ip_address is not None:
            clean_ip = req.ip_address.strip()
            if clean_ip != device.ip_address:
                conflict = (
                    db.query(DeviceModel)
                    .filter(DeviceModel.ip_address == clean_ip, DeviceModel.id != device_id)
                    .first()
                )
                if conflict:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Device with IP address '{clean_ip}' is already registered (device '{conflict.name}').",
                    )
                device.ip_address = clean_ip

        if req.name is not None:
            device.name = req.name.strip()
        if req.device_type is not None:
            device.device_type = req.device_type.strip().lower()
        if req.building is not None:
            device.building = req.building.strip()
        if req.department is not None:
            device.department = req.department.strip()
        if req.floor is not None:
            device.floor = req.floor.strip()
        if req.location_description is not None:
            device.location_description = req.location_description.strip() if req.location_description else None
        if req.vendor_model is not None:
            device.vendor_model = req.vendor_model.strip() if req.vendor_model else None
        if req.collection_method is not None:
            device.collection_method = req.collection_method.strip().lower()
        if req.monitoring_status is not None:
            device.monitoring_status = req.monitoring_status.strip().lower()
        if req.connection_status is not None:
            device.connection_status = req.connection_status.strip().lower()

        device.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(device)
        logger.info("Updated device '%s' (ID %s)", device.name, device.id)
        return device

    def delete_device(self, db: Session, device_id: str) -> bool:
        """Remove a device record and its telemetry history from the registry."""
        device = db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
        if not device:
            return False

        # Clean up associated telemetry records
        db.query(DeviceTelemetryModel).filter(DeviceTelemetryModel.device_id == device_id).delete()
        # Clean up associated topology links and discovery status
        db.query(TopologyLinkModel).filter(
            or_(
                TopologyLinkModel.source_device_id == device_id,
                TopologyLinkModel.remote_device_id == device_id,
            )
        ).delete()
        db.query(TopologyDiscoveryStatusModel).filter(TopologyDiscoveryStatusModel.device_id == device_id).delete()
        db.delete(device)
        db.commit()
        logger.info("Deleted device ID %s and associated telemetry and topology records.", device_id)
        return True

    def get_summary(self, db: Session) -> DeviceSummaryResponse:
        """Compute aggregate counts by category, location, and operational status."""
        devices = db.query(DeviceModel).all()

        total = len(devices)
        online = sum(1 for d in devices if d.connection_status == "online")
        offline = sum(1 for d in devices if d.connection_status == "offline")
        unknown = sum(1 for d in devices if d.connection_status == "unknown")

        active = sum(1 for d in devices if d.monitoring_status == "active")
        inactive = sum(1 for d in devices if d.monitoring_status == "inactive")
        maintenance = sum(1 for d in devices if d.monitoring_status == "maintenance")

        by_type = dict(Counter(d.device_type for d in devices))
        by_dept = dict(Counter(d.department for d in devices))
        by_bldg = dict(Counter(d.building for d in devices))
        by_status = dict(Counter(d.monitoring_status for d in devices))
        by_method = dict(Counter(d.collection_method for d in devices))

        return DeviceSummaryResponse(
            total_devices=total,
            online_count=online,
            offline_count=offline,
            unknown_count=unknown,
            active_count=active,
            inactive_count=inactive,
            maintenance_count=maintenance,
            by_type=by_type,
            by_department=by_dept,
            by_building=by_bldg,
            by_status=by_status,
            by_collection_method=by_method,
        )

    def get_latest_telemetry(
        self,
        db: Session,
        device_id: str,
        interface_name: Optional[str] = None,
    ) -> Optional[DeviceTelemetryModel]:
        """Fetch the most recent telemetry sample for a device."""
        query = db.query(DeviceTelemetryModel).filter(DeviceTelemetryModel.device_id == device_id)
        if interface_name:
            query = query.filter(DeviceTelemetryModel.interface_name == interface_name)
        return query.order_by(DeviceTelemetryModel.timestamp.desc()).first()

    def get_telemetry_history(
        self,
        db: Session,
        device_id: str,
        limit: int = 50,
        interface_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[DeviceTelemetryModel]:
        """Query bounded telemetry history records for a remote device."""
        query = db.query(DeviceTelemetryModel).filter(DeviceTelemetryModel.device_id == device_id)
        if interface_name:
            query = query.filter(DeviceTelemetryModel.interface_name == interface_name)
        if start_time:
            query = query.filter(DeviceTelemetryModel.timestamp >= start_time)
        if end_time:
            query = query.filter(DeviceTelemetryModel.timestamp <= end_time)

        return query.order_by(DeviceTelemetryModel.timestamp.desc()).limit(min(500, max(1, limit))).all()

    def get_campus_telemetry_summary(self, db: Session) -> CampusTelemetrySummaryResponse:
        """Compute aggregate campus telemetry throughput, reachability, and errors."""
        devices = db.query(DeviceModel).all()
        now = datetime.now(timezone.utc)

        total_devs = len(devices)
        polling_enabled_count = sum(1 for d in devices if d.polling_enabled)
        reachable_count = sum(1 for d in devices if d.reachability == "reachable")
        unreachable_count = sum(1 for d in devices if d.reachability == "unreachable")
        configured_count = sum(1 for d in devices if d.reachability == "configured")
        unsupported_count = sum(1 for d in devices if d.reachability == "unsupported")

        total_samples = db.query(DeviceTelemetryModel).count()

        # Sum latest upload/download mbps for each device with recent telemetry
        latest_up = 0.0
        latest_down = 0.0
        total_errors = 0
        total_discards = 0

        # Phase 3 Status Classification
        online_count = 0
        unreach_count = 0
        stale_count = 0
        unknown_count = 0
        maint_count = 0
        polling_errors_count = 0
        last_success_poll: Optional[datetime] = None

        for d in devices:
            if d.monitoring_status == "maintenance":
                maint_count += 1
            elif not d.last_poll_at:
                unknown_count += 1
            else:
                last_poll = d.last_poll_at
                if last_poll.tzinfo is None:
                    last_poll = last_poll.replace(tzinfo=timezone.utc)
                elapsed = (now - last_poll).total_seconds()
                stale_threshold = max(300.0, (d.polling_interval_seconds or 10.0) * 3)

                if d.reachability == "unreachable" or d.last_poll_status == "error":
                    unreach_count += 1
                    polling_errors_count += 1
                elif elapsed > stale_threshold:
                    stale_count += 1
                elif d.reachability == "reachable" and d.last_poll_status == "success":
                    online_count += 1
                    if last_success_poll is None or last_poll > last_success_poll:
                        last_success_poll = last_poll
                else:
                    unknown_count += 1

            # Fetch latest telemetry for throughput sum
            latest = (
                db.query(DeviceTelemetryModel)
                .filter(DeviceTelemetryModel.device_id == d.id)
                .order_by(DeviceTelemetryModel.timestamp.desc())
                .first()
            )
            if latest:
                latest_up += latest.upload_mbps
                latest_down += latest.download_mbps
                total_errors += latest.errors_in + latest.errors_out
                total_discards += latest.discards_in + latest.discards_out

        return CampusTelemetrySummaryResponse(
            total_devices=total_devs,
            polling_enabled_count=polling_enabled_count,
            reachable_count=reachable_count,
            unreachable_count=unreachable_count,
            configured_count=configured_count,
            unsupported_count=unsupported_count,
            online_count=online_count,
            stale_count=stale_count,
            unknown_count=unknown_count,
            maintenance_count=maint_count,
            last_successful_poll=last_success_poll,
            total_polling_errors=polling_errors_count,
            total_telemetry_samples=total_samples,
            latest_campus_upload_mbps=round(latest_up, 4),
            latest_campus_download_mbps=round(latest_down, 4),
            total_errors=total_errors,
            total_discards=total_discards,
            timestamp=now,
        )

    def get_campus_hierarchy(self, db: Session) -> CampusHierarchyResponse:
        """Construct multi-tier campus hierarchy: Campus -> Building -> Floor -> Department -> Device."""
        devices = db.query(DeviceModel).all()
        now = datetime.now(timezone.utc)

        # Structure: buildings[bldg][floor][dept] = list of devices
        tree: Dict[str, Dict[str, Dict[str, List[CampusDeviceNode]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )

        all_depts = set()
        for d in devices:
            all_depts.add(d.department)

            # Determine reliable runtime status
            is_stale = False
            computed_status = "unknown"
            if d.monitoring_status == "maintenance":
                computed_status = "maintenance"
            elif not d.last_poll_at:
                computed_status = "unknown" if d.reachability == "configured" else d.reachability
            else:
                last_poll = d.last_poll_at
                if last_poll.tzinfo is None:
                    last_poll = last_poll.replace(tzinfo=timezone.utc)
                elapsed = (now - last_poll).total_seconds()
                stale_threshold = max(300.0, (d.polling_interval_seconds or 10.0) * 3)
                is_stale = elapsed > stale_threshold

                if d.reachability == "unreachable":
                    computed_status = "unreachable"
                elif d.reachability == "unsupported":
                    computed_status = "unsupported"
                elif d.reachability == "reachable" and d.last_poll_status == "success":
                    computed_status = "stale" if is_stale else "online"
                elif is_stale:
                    computed_status = "stale"
                else:
                    computed_status = d.connection_status or "unknown"

            # Query latest telemetry
            latest_tel = (
                db.query(DeviceTelemetryModel)
                .filter(DeviceTelemetryModel.device_id == d.id)
                .order_by(DeviceTelemetryModel.timestamp.desc())
                .first()
            )

            up_mbps = latest_tel.upload_mbps if latest_tel else 0.0
            down_mbps = latest_tel.download_mbps if latest_tel else 0.0
            oper_st = latest_tel.oper_status if latest_tel else "unknown"

            node = CampusDeviceNode(
                id=d.id,
                name=d.name,
                ip_address=d.ip_address,
                device_type=d.device_type,
                vendor_model=d.vendor_model,
                collection_method=d.collection_method,
                monitoring_status=d.monitoring_status,
                connection_status=d.connection_status,
                reachability=d.reachability,
                computed_status=computed_status,
                is_stale=is_stale,
                polling_enabled=d.polling_enabled,
                polling_interval_seconds=d.polling_interval_seconds,
                last_poll_at=d.last_poll_at,
                latest_upload_mbps=up_mbps,
                latest_download_mbps=down_mbps,
                latest_oper_status=oper_st,
            )
            tree[d.building][d.floor][d.department].append(node)

        # Assemble hierarchical response models
        building_nodes: List[CampusBuildingNode] = []
        for bldg_name, floors in sorted(tree.items()):
            floor_nodes: List[CampusFloorNode] = []
            bldg_total = 0
            bldg_online = 0
            bldg_unreach = 0

            for floor_name, depts in sorted(floors.items()):
                dept_nodes: List[CampusDepartmentNode] = []
                floor_total = 0
                floor_online = 0

                for dept_name, dev_list in sorted(depts.items()):
                    dept_online = sum(1 for dev in dev_list if dev.computed_status == "online")
                    dept_unreach = sum(1 for dev in dev_list if dev.computed_status == "unreachable")
                    dept_nodes.append(
                        CampusDepartmentNode(
                            department=dept_name,
                            total_devices=len(dev_list),
                            online_devices=dept_online,
                            unreachable_devices=dept_unreach,
                            devices=dev_list,
                        )
                    )
                    floor_total += len(dev_list)
                    floor_online += dept_online

                bldg_total += floor_total
                bldg_online += floor_online
                bldg_unreach += sum(d.unreachable_devices for d in dept_nodes)

                floor_nodes.append(
                    CampusFloorNode(
                        floor=floor_name,
                        total_devices=floor_total,
                        online_devices=floor_online,
                        departments=dept_nodes,
                    )
                )

            building_nodes.append(
                CampusBuildingNode(
                    building=bldg_name,
                    total_devices=bldg_total,
                    online_devices=bldg_online,
                    unreachable_devices=bldg_unreach,
                    floors=floor_nodes,
                )
            )

        return CampusHierarchyResponse(
            campus_name="Main University Campus",
            total_devices=len(devices),
            total_buildings=len(building_nodes),
            total_departments=len(all_depts),
            buildings=building_nodes,
            timestamp=now,
        )

    def get_campus_timeline(self, db: Session, hours: int = 1) -> CampusTimelineResponse:
        """Compute chronological aggregated campus throughput timeline within the requested window."""
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=max(1, min(168, hours)))

        samples = (
            db.query(DeviceTelemetryModel)
            .filter(DeviceTelemetryModel.timestamp >= since)
            .order_by(DeviceTelemetryModel.timestamp.asc())
            .all()
        )

        # Decide bucket resolution:
        # <= 2h: 1-minute buckets; <= 12h: 5-minute buckets; > 12h: 15-minute buckets
        bucket_seconds = 60 if hours <= 2 else (300 if hours <= 12 else 900)

        buckets: Dict[int, Dict[str, Any]] = defaultdict(
            lambda: {"up_mbps": 0.0, "down_mbps": 0.0, "samples": 0, "devices": set(), "first_ts": None}
        )

        for s in samples:
            ts = s.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            epoch = int(ts.timestamp())
            b_key = (epoch // bucket_seconds) * bucket_seconds

            b = buckets[b_key]
            if b["first_ts"] is None:
                b["first_ts"] = datetime.fromtimestamp(b_key, tz=timezone.utc).isoformat()
            b["up_mbps"] += s.upload_mbps
            b["down_mbps"] += s.download_mbps
            b["samples"] += 1
            b["devices"].add(s.device_id)

        timeline_points = [
            CampusTimelinePoint(
                timestamp=b["first_ts"] or datetime.fromtimestamp(k, tz=timezone.utc).isoformat(),
                upload_mbps=round(b["up_mbps"], 4),
                download_mbps=round(b["down_mbps"], 4),
                sample_count=b["samples"],
                reporting_devices=len(b["devices"]),
            )
            for k, b in sorted(buckets.items())
        ]

        range_label = f"{hours}h" if hours < 24 else f"{hours // 24}d"
        return CampusTimelineResponse(
            time_range=range_label,
            total_samples=len(samples),
            timeline=timeline_points,
            timestamp=now,
        )

    def get_device_comparison(self, db: Session) -> DeviceComparisonResponse:
        """Compile a flat device-level metric comparison across all registered campus devices."""
        devices = db.query(DeviceModel).all()
        now = datetime.now(timezone.utc)

        items: List[DeviceComparisonItem] = []
        for d in devices:
            is_stale = False
            computed_status = "unknown"
            if d.monitoring_status == "maintenance":
                computed_status = "maintenance"
            elif not d.last_poll_at:
                computed_status = "unknown" if d.reachability == "configured" else d.reachability
            else:
                last_poll = d.last_poll_at
                if last_poll.tzinfo is None:
                    last_poll = last_poll.replace(tzinfo=timezone.utc)
                elapsed = (now - last_poll).total_seconds()
                stale_threshold = max(300.0, (d.polling_interval_seconds or 10.0) * 3)
                is_stale = elapsed > stale_threshold

                if d.reachability == "unreachable":
                    computed_status = "unreachable"
                elif d.reachability == "unsupported":
                    computed_status = "unsupported"
                elif d.reachability == "reachable" and d.last_poll_status == "success":
                    computed_status = "stale" if is_stale else "online"
                elif is_stale:
                    computed_status = "stale"
                else:
                    computed_status = d.connection_status or "unknown"

            latest = (
                db.query(DeviceTelemetryModel)
                .filter(DeviceTelemetryModel.device_id == d.id)
                .order_by(DeviceTelemetryModel.timestamp.desc())
                .first()
            )

            items.append(
                DeviceComparisonItem(
                    device_id=d.id,
                    name=d.name,
                    ip_address=d.ip_address,
                    device_type=d.device_type,
                    building=d.building,
                    floor=d.floor,
                    department=d.department,
                    collection_method=d.collection_method,
                    computed_status=computed_status,
                    reachability=d.reachability,
                    polling_enabled=d.polling_enabled,
                    upload_mbps=latest.upload_mbps if latest else 0.0,
                    download_mbps=latest.download_mbps if latest else 0.0,
                    packets_sent_per_sec=latest.packets_sent_per_sec if latest else 0.0,
                    packets_recv_per_sec=latest.packets_recv_per_sec if latest else 0.0,
                    errors=(latest.errors_in + latest.errors_out) if latest else 0,
                    discards=(latest.discards_in + latest.discards_out) if latest else 0,
                    last_poll_at=d.last_poll_at,
                )
            )

        return DeviceComparisonResponse(
            total_devices=len(items),
            devices=items,
            timestamp=now,
        )


device_service = DeviceRegistryService()
