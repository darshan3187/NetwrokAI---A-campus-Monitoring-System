"""SQLAlchemy ORM models for network metrics persistence."""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Text
from app.database import Base


class NetworkMetricModel(Base):
    """Stores a single network telemetry sample in SQLite.

    All timestamps are stored in UTC. Metrics represent rates calculated over
    actual sample intervals, cumulative data since interface boot, and session
    data since service launch.
    """

    __tablename__ = "network_metrics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        default=lambda: datetime.now(timezone.utc),
    )
    interface = Column(String(100), nullable=False, index=True)
    upload_mbps = Column(Float, nullable=False, default=0.0)
    download_mbps = Column(Float, nullable=False, default=0.0)
    packets_sent_per_sec = Column(Float, nullable=False, default=0.0)
    packets_received_per_sec = Column(Float, nullable=False, default=0.0)
    cumulative_sent_mb = Column(Float, nullable=False, default=0.0)
    cumulative_received_mb = Column(Float, nullable=False, default=0.0)
    session_transferred_mb = Column(Float, nullable=False, default=0.0)

    # Composite index for efficient interface-specific time-range queries
    __table_args__ = (
        Index("idx_interface_timestamp", "interface", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<NetworkMetric(id={self.id}, interface='{self.interface}', "
            f"up={self.upload_mbps:.2f}Mbps, down={self.download_mbps:.2f}Mbps, "
            f"time='{self.timestamp}')>"
        )


class AnomalyEventModel(Base):
    """Stores detected network anomaly events in SQLite.

    Captures timestamp, network interface, normalized anomaly score, severity category,
    detection method, metric snapshot, and human-readable explanation.
    """

    __tablename__ = "anomaly_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        default=lambda: datetime.now(timezone.utc),
    )
    interface = Column(String(100), nullable=False, index=True)
    anomaly_score = Column(Float, nullable=False)
    severity = Column(String(50), nullable=False, index=True)
    detection_method = Column(String(50), nullable=False)
    metrics_snapshot = Column(Text, nullable=False, default="{}")
    explanation = Column(String(500), nullable=False)

    __table_args__ = (
        Index("idx_anomaly_interface_timestamp", "interface", "timestamp"),
        Index("idx_anomaly_severity", "severity"),
    )

    def __repr__(self) -> str:
        return (
            f"<AnomalyEvent(id={self.id}, interface='{self.interface}', "
            f"score={self.anomaly_score:.2f}, severity='{self.severity}', "
            f"time='{self.timestamp}')>"
        )


class DeviceModel(Base):
    """Stores campus network devices in SQLite registry for multi-device monitoring.

    Captures device metadata, location hierarchy (building, department, floor),
    monitoring configuration, and operational status without storing sensitive
    credentials in plaintext.
    """

    __tablename__ = "devices"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False, unique=True, index=True)
    device_type = Column(String(50), nullable=False, index=True)  # router, switch, access_point, server, host, other
    building = Column(String(100), nullable=False, index=True)
    department = Column(String(100), nullable=False, index=True)
    floor = Column(String(50), nullable=False)
    location_description = Column(String(255), nullable=True)
    vendor_model = Column(String(100), nullable=True)
    collection_method = Column(String(50), nullable=False, default="manual")  # local_psutil, snmp, netflow, api, manual
    monitoring_status = Column(String(50), nullable=False, default="active", index=True)  # active, inactive, maintenance
    connection_status = Column(String(50), nullable=False, default="unknown", index=True)  # online, offline, unknown
    
    # Remote polling runtime fields (Phase 2)
    last_poll_at = Column(DateTime(timezone=True), nullable=True)
    last_poll_status = Column(String(50), nullable=True)  # success, error, timeout, unreachable
    last_poll_error = Column(String(255), nullable=True)
    reachability = Column(String(50), nullable=False, default="configured", index=True)  # configured, reachable, unreachable, unsupported
    polling_enabled = Column(Boolean, nullable=False, default=False, index=True)
    polling_interval_seconds = Column(Float, nullable=False, default=10.0)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_device_dept_bldg", "department", "building"),
        Index("idx_device_type_status", "device_type", "monitoring_status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Device(id='{self.id}', name='{self.name}', ip='{self.ip_address}', "
            f"type='{self.device_type}', reachability='{self.reachability}')>"
        )


class DeviceTelemetryModel(Base):
    """Stores periodic telemetry samples collected from remote campus devices.

    Kept strictly separated from local host telemetry (`network_metrics`) and
    simulation metrics to maintain pristine data provenance and isolation.
    """

    __tablename__ = "device_telemetry"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_id = Column(String(64), nullable=False, index=True)
    interface_index = Column(Integer, nullable=True)
    interface_name = Column(String(100), nullable=False, default="default", index=True)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        default=lambda: datetime.now(timezone.utc),
    )
    bytes_sent = Column(Float, nullable=False, default=0.0)
    bytes_recv = Column(Float, nullable=False, default=0.0)
    packets_sent = Column(Float, nullable=False, default=0.0)
    packets_recv = Column(Float, nullable=False, default=0.0)
    upload_mbps = Column(Float, nullable=False, default=0.0)
    download_mbps = Column(Float, nullable=False, default=0.0)
    packets_sent_per_sec = Column(Float, nullable=False, default=0.0)
    packets_recv_per_sec = Column(Float, nullable=False, default=0.0)
    errors_in = Column(Integer, nullable=False, default=0)
    errors_out = Column(Integer, nullable=False, default=0)
    discards_in = Column(Integer, nullable=False, default=0)
    discards_out = Column(Integer, nullable=False, default=0)
    collection_method = Column(String(50), nullable=False, default="manual")
    data_validity = Column(String(50), nullable=False, default="valid")  # valid, initial_sample, counter_reset, error, mock
    oper_status = Column(String(20), nullable=False, default="up")  # up, down, unknown

    __table_args__ = (
        Index("idx_dev_telemetry_device_time", "device_id", "timestamp"),
        Index("idx_dev_telemetry_dev_iface_time", "device_id", "interface_name", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<DeviceTelemetry(id={self.id}, device='{self.device_id}', iface='{self.interface_name}', "
            f"up={self.upload_mbps:.2f}Mbps, down={self.download_mbps:.2f}Mbps, time='{self.timestamp}')>"
        )


class TopologyLinkModel(Base):
    """Stores discovered physical and logical link connections between network devices.

    Captured via read-only LLDP (IEEE 802.1AB) and CDP protocols.
    Supports both resolved links (mapped to a registered campus device) and unresolved
    neighbors (external, unmanaged, or third-party devices) without fabricating device records.
    """

    __tablename__ = "topology_links"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    source_device_id = Column(String(64), nullable=False, index=True)
    local_interface = Column(String(100), nullable=False)
    remote_device_id = Column(String(64), nullable=True, index=True)
    remote_chassis_id = Column(String(255), nullable=False)
    remote_chassis_id_subtype = Column(String(50), nullable=True)
    remote_port_id = Column(String(255), nullable=False)
    remote_port_id_subtype = Column(String(50), nullable=True)
    remote_port_desc = Column(String(255), nullable=True)
    remote_system_name = Column(String(255), nullable=True)
    remote_system_desc = Column(String(500), nullable=True)
    protocol = Column(String(20), nullable=False, default="lldp")  # lldp, cdp
    discovered_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_seen_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    discovery_source = Column(String(50), nullable=False, default="snmp")  # snmp, mock
    resolution_state = Column(String(50), nullable=False, default="unresolved", index=True)  # resolved, unresolved
    link_status = Column(String(20), nullable=False, default="active", index=True)  # active, stale, down

    __table_args__ = (
        Index("idx_topo_src_local_remote", "source_device_id", "local_interface", "remote_chassis_id", "remote_port_id", unique=True),
        Index("idx_topo_link_status_res", "link_status", "resolution_state"),
    )

    def __repr__(self) -> str:
        return (
            f"<TopologyLink(id={self.id}, src='{self.source_device_id}:{self.local_interface}', "
            f"remote='{self.remote_device_id or self.remote_chassis_id}:{self.remote_port_id}', "
            f"proto='{self.protocol}', status='{self.link_status}')>"
        )


class TopologyDiscoveryStatusModel(Base):
    """Tracks the operational discovery state and protocol support for each device."""

    __tablename__ = "topology_discovery_status"

    device_id = Column(String(64), primary_key=True, index=True)
    status = Column(String(50), nullable=False, default="idle")  # idle, in_progress, success, failed, unsupported, empty
    protocol = Column(String(20), nullable=False, default="lldp")  # lldp, cdp, both
    lldp_supported = Column(Boolean, nullable=False, default=False)
    cdp_supported = Column(Boolean, nullable=False, default=False)
    discovered_neighbors_count = Column(Integer, nullable=False, default=0)
    resolved_neighbors_count = Column(Integer, nullable=False, default=0)
    last_discovery_at = Column(DateTime(timezone=True), nullable=True)
    last_discovery_duration_ms = Column(Float, nullable=True)
    last_error = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<TopologyDiscoveryStatus(device='{self.device_id}', status='{self.status}', "
            f"lldp={self.lldp_supported}, cdp={self.cdp_supported})>"
        )


class TopologyAlertModel(Base):
    """Stores topology change detection events and operational alert records (Phase 6).

    Preserves full audit trail for discovered network topology changes, including
    new neighbors, stale observations, link restorations, interface shifts, and protocol changes.
    Tracks lifecycle transitions (open -> acknowledged -> resolved) without mutating historical topology links.
    """

    __tablename__ = "topology_alerts"

    id = Column(String(64), primary_key=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    # new_neighbor, neighbor_stale, neighbor_restored, interface_changed, protocol_changed, discovery_failed, discovery_unsupported
    severity = Column(String(20), nullable=False, default="info", index=True)
    # info, warning, critical, error
    status = Column(String(20), nullable=False, default="open", index=True)
    # open, acknowledged, resolved
    source_device_id = Column(String(64), nullable=False, index=True)
    source_device_name = Column(String(255), nullable=True)
    remote_device_id = Column(String(64), nullable=True, index=True)
    remote_device_name = Column(String(255), nullable=True)
    remote_chassis_id = Column(String(255), nullable=True)
    local_interface = Column(String(100), nullable=True)
    remote_port_id = Column(String(255), nullable=True)
    protocol = Column(String(20), nullable=True)
    message = Column(String(500), nullable=False)
    details = Column(Text, nullable=True)
    first_detected_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    last_seen_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    acknowledgement_note = Column(String(500), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(100), nullable=True)
    resolution_note = Column(String(500), nullable=True)
    occurrence_count = Column(Integer, nullable=False, default=1)
    is_mock = Column(Boolean, nullable=False, default=False, index=True)
    discovery_source = Column(String(50), nullable=False, default="snmp")

    __table_args__ = (
        Index("idx_alert_status_sev", "status", "severity"),
        Index("idx_alert_src_event", "source_device_id", "event_type"),
        Index("idx_alert_status_event", "status", "event_type"),
        Index("idx_alert_dedup", "source_device_id", "event_type", "local_interface", "remote_chassis_id", "is_mock", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<TopologyAlert(id='{self.id}', type='{self.event_type}', status='{self.status}', "
            f"severity='{self.severity}', src='{self.source_device_id}', count={self.occurrence_count})>"
        )



