import ipaddress
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HealthResponse(BaseModel):
    """System health check and component connectivity status."""

    status: str = Field(..., description="Overall service status (e.g., 'ok', 'degraded')")
    database: str = Field(..., description="Database connectivity status")
    monitoring: str = Field(..., description="Background collector state ('running', 'stopped')")
    active_interface: Optional[str] = Field(None, description="Currently monitored interface")
    timestamp: datetime = Field(..., description="Current server time in UTC")


class InterfaceDetail(BaseModel):
    """Information for a single network interface."""

    name: str = Field(..., description="System interface identifier (e.g., 'Wi-Fi', 'eth0')")
    bytes_sent: int = Field(..., ge=0, description="Lifetime bytes sent")
    bytes_recv: int = Field(..., ge=0, description="Lifetime bytes received")
    packets_sent: int = Field(..., ge=0, description="Lifetime packets sent")
    packets_recv: int = Field(..., ge=0, description="Lifetime packets received")
    is_up: bool = Field(True, description="Whether interface link is active")
    speed_mbps: Optional[int] = Field(None, description="Link speed in Mbps, if reported by OS")


class InterfaceListResponse(BaseModel):
    """List of all available network interfaces detected on the host."""

    interfaces: List[str] = Field(..., description="Names of all detected interfaces")
    details: List[InterfaceDetail] = Field(default_factory=list, description="Detailed stats per interface")
    active_interface: Optional[str] = Field(None, description="Interface currently selected for monitoring")
    count: int = Field(..., ge=0, description="Total number of detected interfaces")


class AnomalyEvaluationSchema(BaseModel):
    """Real-time AI anomaly evaluation result for streaming metrics."""

    score: float = Field(..., ge=0.0, le=1.0, description="Normalized anomaly score (0.0 to 1.0)")
    severity: str = Field(..., description="Severity category ('Normal', 'Unusual Traffic', 'High Anomaly')")
    is_anomaly: bool = Field(..., description="True if behavior is unusual or high anomaly")
    method: str = Field(..., description="Detection method ('isolation_forest', 'statistical_fallback', 'warmup')")
    explanation: str = Field(..., description="Human-readable behavioral explanation")


class NetworkMetricResponse(BaseModel):
    """Network telemetry sample with throughput and packet rates."""

    id: Optional[int] = Field(None, description="Database record ID (if persisted)")
    timestamp: datetime = Field(..., description="UTC timestamp of the sample")
    interface: str = Field(..., description="Interface name")
    upload_mbps: float = Field(..., ge=0.0, description="Instantaneous upload throughput in Mbps")
    download_mbps: float = Field(..., ge=0.0, description="Instantaneous download throughput in Mbps")
    packets_sent_per_sec: float = Field(..., ge=0.0, description="Packets transmitted per second")
    packets_received_per_sec: float = Field(..., ge=0.0, description="Packets received per second")
    cumulative_sent_mb: float = Field(..., ge=0.0, description="Cumulative MB sent since adapter boot")
    cumulative_received_mb: float = Field(..., ge=0.0, description="Cumulative MB received since adapter boot")
    session_transferred_mb: float = Field(..., ge=0.0, description="Total MB transferred during this session")
    is_initial_sample: Optional[bool] = Field(False, description="True if baseline/initialization sample")
    anomaly: Optional[AnomalyEvaluationSchema] = Field(None, description="Real-time AI anomaly evaluation")

    model_config = ConfigDict(from_attributes=True)



class HistoricalMetricsResponse(BaseModel):
    """Historical network metrics query result."""

    interface: Optional[str] = Field(None, description="Interface filtered by, or None for all")
    total_returned: int = Field(..., ge=0, description="Number of metric records in this response")
    limit: int = Field(..., ge=1, description="Requested sample limit")
    metrics: List[NetworkMetricResponse] = Field(default_factory=list, description="List of metric records")


class MonitoringSummaryResponse(BaseModel):
    """Comprehensive summary of monitoring statistics and peaks."""

    interface: Optional[str] = Field(None, description="Target monitored interface")
    is_monitoring: bool = Field(..., description="Whether monitoring loop is active")
    current_upload_mbps: float = Field(..., ge=0.0, description="Latest upload throughput")
    current_download_mbps: float = Field(..., ge=0.0, description="Latest download throughput")
    peak_upload_mbps: float = Field(..., ge=0.0, description="Peak upload throughput observed in session")
    peak_download_mbps: float = Field(..., ge=0.0, description="Peak download throughput observed in session")
    session_transferred_mb: float = Field(..., ge=0.0, description="Session transferred data in MB")
    cumulative_sent_mb: float = Field(..., ge=0.0, description="Lifetime total sent in MB")
    cumulative_received_mb: float = Field(..., ge=0.0, description="Lifetime total received in MB")
    total_stored_samples: int = Field(..., ge=0, description="Total samples in SQLite database")
    session_samples_collected: int = Field(..., ge=0, description="Samples collected in current run")
    monitoring_duration_seconds: float = Field(..., ge=0.0, description="Seconds monitoring has been active")


class MonitoringControlRequest(BaseModel):
    """Request payload to change monitoring target or sampling interval."""

    interface: Optional[str] = Field(None, description="Interface name to switch monitoring to")
    interval_seconds: Optional[float] = Field(1.0, ge=0.1, le=60.0, description="Polling interval in seconds")


class AnomalyEventResponse(BaseModel):
    """Persisted anomaly event record."""

    id: int = Field(..., description="Event database ID")
    timestamp: datetime = Field(..., description="UTC timestamp of the detected event")
    interface: str = Field(..., description="Network interface name")
    anomaly_score: float = Field(..., ge=0.0, le=1.0, description="Normalized anomaly score (0.0 to 1.0)")
    severity: str = Field(..., description="Severity category ('Unusual Traffic', 'High Anomaly')")
    detection_method: str = Field(..., description="Detection algorithm used")
    metrics_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Snapshot of telemetry and features")
    explanation: str = Field(..., description="Human-readable explanation of detected behavior")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("metrics_snapshot", mode="before")
    @classmethod
    def parse_metrics_snapshot(cls, v: Any) -> Dict[str, Any]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        if isinstance(v, dict):
            return v
        return {}


class AnomalyListResponse(BaseModel):
    """List of persisted anomaly events with query pagination metadata."""

    total_returned: int = Field(..., ge=0, description="Total events in this response")
    limit: int = Field(..., ge=1, description="Requested query limit")
    events: List[AnomalyEventResponse] = Field(default_factory=list, description="List of anomaly event records")


class AnomalySummaryResponse(BaseModel):
    """Summary of anomaly detection engine status and cumulative event statistics."""

    total_anomalies: int = Field(..., ge=0, description="Total anomaly events stored in database")
    unusual_traffic_count: int = Field(..., ge=0, description="Count of 'Unusual Traffic' events")
    high_anomaly_count: int = Field(..., ge=0, description="Count of 'High Anomaly' events")
    latest_anomaly: Optional[AnomalyEventResponse] = Field(None, description="Most recent anomaly event, if any")
    model_status: str = Field(..., description="Model state ('active', 'warming_up', 'ready_to_train')")
    is_trained: bool = Field(..., description="Whether Isolation Forest is fitted and active")
    samples_observed: int = Field(..., ge=0, description="Total telemetry samples processed by engine")
    active_interface: Optional[str] = Field(None, description="Interface evaluated by the engine")


# ============================================================================
# Simulation Schemas
# ============================================================================


class ScenarioMetaResponse(BaseModel):
    """Metadata describing a controlled simulation scenario."""

    scenario_id: str = Field(..., description="Unique scenario identifier")
    name: str = Field(..., description="Human-readable scenario name")
    category: str = Field(..., description="Classification category (e.g., Baseline, Throughput)")
    description: str = Field(..., description="Detailed description of simulated traffic behavior")
    duration_seconds: int = Field(..., ge=1, description="Scenario duration in seconds/steps")
    expected_behavior: str = Field(..., description="Expected model detection outcome")


class ScenarioListResponse(BaseModel):
    """List of all available simulation scenarios."""

    scenarios: List[ScenarioMetaResponse] = Field(default_factory=list, description="Registered simulation scenarios")
    count: int = Field(..., ge=0, description="Number of registered scenarios")


class SimulationRunRequest(BaseModel):
    """Request payload to initiate a controlled simulation run."""

    scenario_id: str = Field(..., description="ID of the scenario to execute")
    seed: Optional[int] = Field(42, description="Deterministic random seed for reproducibility")


class ConfusionMatrixSchema(BaseModel):
    """2x2 confusion matrix outcome."""

    true_positives: int = Field(..., ge=0, description="True Positive count")
    true_negatives: int = Field(..., ge=0, description="True Negative count")
    false_positives: int = Field(..., ge=0, description="False Positive count")
    false_negatives: int = Field(..., ge=0, description="False Negative count")
    total_samples: int = Field(..., ge=0, description="Total samples evaluated")


class ValidationMetricsSchema(BaseModel):
    """Computed statistical validation performance metrics."""

    precision: Optional[float] = Field(None, ge=0.0, le=1.0, description="Precision score TP / (TP + FP) or null if undefined")
    recall: Optional[float] = Field(None, ge=0.0, le=1.0, description="Recall score TP / (TP + FN) or null if undefined")
    f1_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Harmonic mean of precision and recall or null if undefined")
    accuracy: float = Field(..., ge=0.0, le=1.0, description="Overall classification accuracy (TP + TN) / Total")
    detection_latency_seconds: Optional[float] = Field(
        None, ge=0.0, description="Elapsed simulation seconds from anomaly onset to first model detection, or null if unreached/not applicable"
    )


class SimulationTimelinePointSchema(BaseModel):
    """Detailed observation at a single time step in the simulation."""

    step: int = Field(..., ge=1, description="Step index (1-based)")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    download_mbps: float = Field(..., ge=0.0, description="Simulated download throughput")
    upload_mbps: float = Field(..., ge=0.0, description="Simulated upload throughput")
    packets_per_sec: float = Field(..., ge=0.0, description="Simulated total packet rate")
    ground_truth_anomaly: bool = Field(..., description="Ground-truth anomaly label")
    expected_severity: str = Field(..., description="Expected severity classification")
    predicted_score: float = Field(..., ge=0.0, le=1.0, description="Anomaly score assigned by detector")
    predicted_severity: str = Field(..., description="Severity category assigned by detector")
    is_detected: bool = Field(..., description="Whether model classified this step as anomalous")
    detection_method: str = Field(..., description="Detection method used (e.g. isolation_forest)")
    explanation: str = Field(..., description="Detector explanation diagnostic")


class SimulationResultResponse(BaseModel):
    """Full validation result of a simulation execution."""

    scenario_id: str = Field(..., description="Executed scenario ID")
    scenario_name: str = Field(..., description="Scenario display name")
    category: str = Field(..., description="Scenario category")
    description: str = Field(..., description="Scenario description")
    seed: int = Field(..., description="Random seed used for generation")
    duration_seconds: int = Field(..., ge=1, description="Total execution duration in seconds")
    evaluated_at: str = Field(..., description="Evaluation timestamp")
    confusion_matrix: ConfusionMatrixSchema = Field(..., description="Evaluation confusion matrix")
    metrics: ValidationMetricsSchema = Field(..., description="Evaluation performance metrics")
    timeline: List[SimulationTimelinePointSchema] = Field(default_factory=list, description="Step-by-step timeline")
    expected_behavior: str = Field(..., description="Expected model outcome")
    disclaimer: str = Field(..., description="Mandatory synthetic simulation disclaimer")


class SimulationResetResponse(BaseModel):
    """Response returned upon clearing simulation state."""

    status: str = Field("ok", description="Operation status")
    message: str = Field(..., description="Status description")


# ============================================================================
# Multi-Device Registry Schemas (Phase 1)
# ============================================================================

ALLOWED_DEVICE_TYPES = {"router", "switch", "access_point", "server", "host", "other"}
ALLOWED_COLLECTION_METHODS = {"local_psutil", "snmp", "netflow", "api", "manual", "mock"}
ALLOWED_MONITORING_STATUSES = {"active", "inactive", "maintenance"}
ALLOWED_CONNECTION_STATUSES = {"online", "offline", "unknown"}


class DeviceCreateRequest(BaseModel):
    """Request payload to register a new network device in the campus registry."""

    id: Optional[str] = Field(None, description="Optional custom device ID; generated if omitted")
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable device name")
    ip_address: str = Field(..., min_length=1, max_length=45, description="Management IPv4 or IPv6 address")
    device_type: str = Field(..., description="Device category (router, switch, access_point, server, host, other)")
    building: str = Field(..., min_length=1, max_length=100, description="Campus building name or code")
    department: str = Field(..., min_length=1, max_length=100, description="Department responsible for device")
    floor: str = Field(..., min_length=1, max_length=50, description="Floor identifier (e.g. '1', '2', 'Ground')")
    location_description: Optional[str] = Field(None, max_length=255, description="Specific room or rack location")
    vendor_model: Optional[str] = Field(None, max_length=100, description="Hardware vendor and model info")
    collection_method: str = Field(
        "manual",
        description="Telemetry collection method (local_psutil, snmp, netflow, api, manual)",
    )
    monitoring_status: str = Field(
        "active",
        description="Monitoring operational state (active, inactive, maintenance)",
    )
    connection_status: str = Field(
        "unknown",
        description="Current connectivity status (online, offline, unknown)",
    )

    @field_validator("name", "building", "department", "floor")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or contain only whitespace.")
        return s

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        s = v.strip()
        try:
            ipaddress.ip_address(s)
        except ValueError:
            raise ValueError(f"Invalid IP address format: '{v}'. Must be a valid IPv4 or IPv6 address.")
        return s

    @field_validator("device_type")
    @classmethod
    def validate_device_type(cls, v: str) -> str:
        s = v.strip().lower()
        if s not in ALLOWED_DEVICE_TYPES:
            raise ValueError(f"Invalid device_type: '{v}'. Must be one of {sorted(ALLOWED_DEVICE_TYPES)}.")
        return s

    @field_validator("collection_method")
    @classmethod
    def validate_collection_method(cls, v: str) -> str:
        s = v.strip().lower()
        if s not in ALLOWED_COLLECTION_METHODS:
            raise ValueError(f"Invalid collection_method: '{v}'. Must be one of {sorted(ALLOWED_COLLECTION_METHODS)}.")
        return s

    @field_validator("monitoring_status")
    @classmethod
    def validate_monitoring_status(cls, v: str) -> str:
        s = v.strip().lower()
        if s not in ALLOWED_MONITORING_STATUSES:
            raise ValueError(f"Invalid monitoring_status: '{v}'. Must be one of {sorted(ALLOWED_MONITORING_STATUSES)}.")
        return s

    @field_validator("connection_status")
    @classmethod
    def validate_connection_status(cls, v: str) -> str:
        s = v.strip().lower()
        if s not in ALLOWED_CONNECTION_STATUSES:
            raise ValueError(f"Invalid connection_status: '{v}'. Must be one of {sorted(ALLOWED_CONNECTION_STATUSES)}.")
        return s


class DeviceUpdateRequest(BaseModel):
    """Request payload to partially update a registered campus network device."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    ip_address: Optional[str] = Field(None, min_length=1, max_length=45)
    device_type: Optional[str] = None
    building: Optional[str] = Field(None, min_length=1, max_length=100)
    department: Optional[str] = Field(None, min_length=1, max_length=100)
    floor: Optional[str] = Field(None, min_length=1, max_length=50)
    location_description: Optional[str] = Field(None, max_length=255)
    vendor_model: Optional[str] = Field(None, max_length=100)
    collection_method: Optional[str] = None
    monitoring_status: Optional[str] = None
    connection_status: Optional[str] = None

    @field_validator("name", "building", "department", "floor")
    @classmethod
    def validate_non_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or contain only whitespace.")
        return s

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        try:
            ipaddress.ip_address(s)
        except ValueError:
            raise ValueError(f"Invalid IP address format: '{v}'. Must be a valid IPv4 or IPv6 address.")
        return s

    @field_validator("device_type")
    @classmethod
    def validate_device_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip().lower()
        if s not in ALLOWED_DEVICE_TYPES:
            raise ValueError(f"Invalid device_type: '{v}'. Must be one of {sorted(ALLOWED_DEVICE_TYPES)}.")
        return s

    @field_validator("collection_method")
    @classmethod
    def validate_collection_method(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip().lower()
        if s not in ALLOWED_COLLECTION_METHODS:
            raise ValueError(f"Invalid collection_method: '{v}'. Must be one of {sorted(ALLOWED_COLLECTION_METHODS)}.")
        return s

    @field_validator("monitoring_status")
    @classmethod
    def validate_monitoring_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip().lower()
        if s not in ALLOWED_MONITORING_STATUSES:
            raise ValueError(f"Invalid monitoring_status: '{v}'. Must be one of {sorted(ALLOWED_MONITORING_STATUSES)}.")
        return s

    @field_validator("connection_status")
    @classmethod
    def validate_connection_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip().lower()
        if s not in ALLOWED_CONNECTION_STATUSES:
            raise ValueError(f"Invalid connection_status: '{v}'. Must be one of {sorted(ALLOWED_CONNECTION_STATUSES)}.")
        return s


class DeviceResponse(BaseModel):
    """Campus network device response representation."""

    id: str = Field(..., description="Unique device identifier")
    name: str = Field(..., description="Device name")
    ip_address: str = Field(..., description="Management IP address")
    device_type: str = Field(..., description="Device category")
    building: str = Field(..., description="Building")
    department: str = Field(..., description="Department")
    floor: str = Field(..., description="Floor")
    location_description: Optional[str] = Field(None, description="Detailed location")
    vendor_model: Optional[str] = Field(None, description="Vendor / Model")
    collection_method: str = Field(..., description="Collection method")
    monitoring_status: str = Field(..., description="Monitoring status")
    connection_status: str = Field(..., description="Connection status")
    
    # Remote polling runtime fields (Phase 2 & 3)
    last_poll_at: Optional[datetime] = Field(None, description="Last successful poll timestamp")
    last_poll_status: Optional[str] = Field(None, description="Status of the last poll attempt")
    last_poll_error: Optional[str] = Field(None, description="Safe sanitized error message from last poll")
    reachability: str = Field("configured", description="Reachability state: configured, reachable, unreachable, unsupported")
    polling_enabled: bool = Field(False, description="Whether active background polling is enabled")
    polling_interval_seconds: float = Field(10.0, ge=1.0, description="Configured polling frequency in seconds")
    
    # Phase 3 Reliable Status Fields
    computed_status: str = Field("unknown", description="Reliable derived operational status: online, unreachable, stale, maintenance, unknown")
    is_stale: bool = Field(False, description="Whether telemetry is older than the staleness threshold")

    created_at: datetime = Field(..., description="Creation UTC timestamp")
    updated_at: datetime = Field(..., description="Last update UTC timestamp")

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def compute_runtime_status(self) -> "DeviceResponse":
        now = datetime.now(timezone.utc)
        if self.monitoring_status == "maintenance":
            self.computed_status = "maintenance"
            return self

        if not self.last_poll_at:
            self.computed_status = "unknown" if self.reachability == "configured" else self.reachability
            return self

        last_poll = self.last_poll_at
        if last_poll.tzinfo is None:
            last_poll = last_poll.replace(tzinfo=timezone.utc)

        elapsed = (now - last_poll).total_seconds()
        stale_threshold = max(300.0, (self.polling_interval_seconds or 10.0) * 3)

        if elapsed > stale_threshold:
            self.is_stale = True

        if self.reachability == "unreachable":
            self.computed_status = "unreachable"
        elif self.reachability == "unsupported":
            self.computed_status = "unsupported"
        elif self.reachability == "reachable" and self.last_poll_status == "success":
            self.computed_status = "stale" if self.is_stale else "online"
        elif self.is_stale:
            self.computed_status = "stale"
        else:
            self.computed_status = self.connection_status or "unknown"

        return self


class DeviceListResponse(BaseModel):
    """List of registered campus network devices."""

    total: int = Field(..., ge=0, description="Total number of registered devices matching filter")
    devices: List[DeviceResponse] = Field(default_factory=list, description="Registered devices")


class DeviceSummaryResponse(BaseModel):
    """Statistical summary of campus device registry."""

    total_devices: int = Field(..., ge=0, description="Total devices registered")
    online_count: int = Field(..., ge=0, description="Devices with online status")
    offline_count: int = Field(..., ge=0, description="Devices with offline status")
    unknown_count: int = Field(..., ge=0, description="Devices with unknown connection status")
    active_count: int = Field(..., ge=0, description="Devices actively monitored")
    inactive_count: int = Field(..., ge=0, description="Devices inactive")
    maintenance_count: int = Field(..., ge=0, description="Devices under maintenance")
    by_type: Dict[str, int] = Field(default_factory=dict, description="Count breakdown by device type")
    by_department: Dict[str, int] = Field(default_factory=dict, description="Count breakdown by department")
    by_building: Dict[str, int] = Field(default_factory=dict, description="Count breakdown by building")
    by_status: Dict[str, int] = Field(default_factory=dict, description="Count breakdown by monitoring status")
    by_collection_method: Dict[str, int] = Field(default_factory=dict, description="Count breakdown by collection method")


# ============================================================================
# Remote Device Telemetry & Health Schemas (Phase 2)
# ============================================================================


class DeviceTelemetryResponse(BaseModel):
    """Telemetry sample collected from a remote campus network device."""

    id: Optional[int] = Field(None, description="Database record ID")
    device_id: str = Field(..., description="Target device identifier")
    interface_index: Optional[int] = Field(None, description="Physical or logical interface index")
    interface_name: str = Field(..., description="Interface name (e.g. 'GigabitEthernet0/1')")
    timestamp: datetime = Field(..., description="Sample UTC timestamp")
    bytes_sent: float = Field(..., ge=0.0, description="Cumulative or raw bytes transmitted")
    bytes_recv: float = Field(..., ge=0.0, description="Cumulative or raw bytes received")
    packets_sent: float = Field(..., ge=0.0, description="Cumulative packets transmitted")
    packets_recv: float = Field(..., ge=0.0, description="Cumulative packets received")
    upload_mbps: float = Field(..., ge=0.0, description="Computed transmission rate in Mbps")
    download_mbps: float = Field(..., ge=0.0, description="Computed reception rate in Mbps")
    packets_sent_per_sec: float = Field(..., ge=0.0, description="Computed packets sent per second")
    packets_recv_per_sec: float = Field(..., ge=0.0, description="Computed packets received per second")
    errors_in: int = Field(0, ge=0, description="Input error count")
    errors_out: int = Field(0, ge=0, description="Output error count")
    discards_in: int = Field(0, ge=0, description="Input discard/drop count")
    discards_out: int = Field(0, ge=0, description="Output discard/drop count")
    collection_method: str = Field(..., description="Collection method used (snmp, mock, local_psutil)")
    data_validity: str = Field(..., description="Data validity flag: valid, initial_sample, counter_reset, mock, error")
    oper_status: str = Field("up", description="Interface operational status: up, down, testing, unknown")

    model_config = ConfigDict(from_attributes=True)


class DeviceTelemetryHistoryResponse(BaseModel):
    """Historical telemetry query result for a remote device."""

    device_id: str = Field(..., description="Target device identifier")
    interface_name: Optional[str] = Field(None, description="Interface filtered by, or None for all")
    total_returned: int = Field(..., ge=0, description="Number of telemetry samples in this response")
    limit: int = Field(..., ge=1, description="Requested sample limit")
    telemetry: List[DeviceTelemetryResponse] = Field(default_factory=list, description="Telemetry records")


class DeviceHealthResponse(BaseModel):
    """Health, connectivity, and polling diagnostics for a single remote device."""

    device_id: str = Field(..., description="Device ID")
    name: str = Field(..., description="Device name")
    ip_address: str = Field(..., description="Management IP address")
    reachability: str = Field(..., description="Reachability state: configured, reachable, unreachable, unsupported")
    polling_enabled: bool = Field(..., description="Whether periodic polling is active")
    polling_interval_seconds: float = Field(..., description="Configured polling cadence")
    last_poll_at: Optional[datetime] = Field(None, description="Timestamp of last poll execution")
    last_poll_status: Optional[str] = Field(None, description="Status of last poll attempt (success, error, timeout)")
    last_poll_error: Optional[str] = Field(None, description="Sanitized error description, if any")
    timestamp: datetime = Field(..., description="Current server time in UTC")


class DeviceMonitoringControlRequest(BaseModel):
    """Request payload to configure or start polling on a device."""

    interval_seconds: Optional[float] = Field(None, ge=1.0, le=300.0, description="Optional polling interval in seconds (1-300)")


class CampusTelemetrySummaryResponse(BaseModel):
    """Aggregate telemetry summary across all monitored campus devices."""

    total_devices: int = Field(..., ge=0, description="Total registered devices")
    polling_enabled_count: int = Field(..., ge=0, description="Devices with active polling enabled")
    reachable_count: int = Field(..., ge=0, description="Devices marked reachable")
    unreachable_count: int = Field(..., ge=0, description="Devices marked unreachable")
    configured_count: int = Field(..., ge=0, description="Devices in configured/standby state")
    unsupported_count: int = Field(..., ge=0, description="Devices with unsupported protocol/OIDs")
    
    # Phase 3 Status Refinements
    online_count: int = Field(0, ge=0, description="Devices actively polling and reachable")
    stale_count: int = Field(0, ge=0, description="Devices with stale telemetry beyond interval threshold")
    unknown_count: int = Field(0, ge=0, description="Devices without sufficient poll evidence")
    maintenance_count: int = Field(0, ge=0, description="Devices under maintenance")
    last_successful_poll: Optional[datetime] = Field(None, description="Timestamp of the most recent successful poll across devices")
    total_polling_errors: int = Field(0, ge=0, description="Number of devices currently exhibiting poll errors")

    total_telemetry_samples: int = Field(..., ge=0, description="Total stored telemetry samples across devices")
    latest_campus_upload_mbps: float = Field(..., ge=0.0, description="Summed latest upload throughput across reachable devices")
    latest_campus_download_mbps: float = Field(..., ge=0.0, description="Summed latest download throughput across reachable devices")
    total_errors: int = Field(..., ge=0, description="Total cumulative error count across devices")
    total_discards: int = Field(..., ge=0, description="Total cumulative discards across devices")
    timestamp: datetime = Field(..., description="Current server time in UTC")


# ============================================================================
# Phase 3: Campus Hierarchy, Timeline, and Device Comparison Schemas
# ============================================================================


class CampusDeviceNode(BaseModel):
    """Leaf node representing an individual device in the campus hierarchy."""

    id: str
    name: str
    ip_address: str
    device_type: str
    vendor_model: Optional[str] = None
    collection_method: str
    monitoring_status: str
    connection_status: str
    reachability: str
    computed_status: str
    is_stale: bool = False
    polling_enabled: bool
    polling_interval_seconds: float
    last_poll_at: Optional[datetime] = None
    latest_upload_mbps: float = 0.0
    latest_download_mbps: float = 0.0
    latest_oper_status: str = "unknown"


class CampusDepartmentNode(BaseModel):
    """Department node grouping devices under a building floor."""

    department: str
    total_devices: int
    online_devices: int
    unreachable_devices: int
    devices: List[CampusDeviceNode] = Field(default_factory=list)


class CampusFloorNode(BaseModel):
    """Floor node grouping departments under a building."""

    floor: str
    total_devices: int
    online_devices: int
    departments: List[CampusDepartmentNode] = Field(default_factory=list)


class CampusBuildingNode(BaseModel):
    """Building node grouping floors and departments."""

    building: str
    total_devices: int
    online_devices: int
    unreachable_devices: int
    floors: List[CampusFloorNode] = Field(default_factory=list)


class CampusHierarchyResponse(BaseModel):
    """Hierarchical campus topology: Campus -> Building -> Floor -> Department -> Device."""

    campus_name: str = "Main University Campus"
    total_devices: int
    total_buildings: int
    total_departments: int
    buildings: List[CampusBuildingNode] = Field(default_factory=list)
    timestamp: datetime


class CampusTimelinePoint(BaseModel):
    """Aggregated campus throughput snapshot across reporting devices."""

    timestamp: str
    upload_mbps: float
    download_mbps: float
    sample_count: int
    reporting_devices: int


class CampusTimelineResponse(BaseModel):
    """Chronological campus-wide aggregate throughput timeline."""

    time_range: str
    total_samples: int
    timeline: List[CampusTimelinePoint] = Field(default_factory=list)
    timestamp: datetime


class DeviceComparisonItem(BaseModel):
    """Individual device metric comparison item for multi-device table/charts."""

    device_id: str
    name: str
    ip_address: str
    device_type: str
    building: str
    floor: str
    department: str
    collection_method: str
    computed_status: str
    reachability: str
    polling_enabled: bool
    upload_mbps: float
    download_mbps: float
    packets_sent_per_sec: float
    packets_recv_per_sec: float
    errors: int
    discards: int
    last_poll_at: Optional[datetime] = None


class DeviceComparisonResponse(BaseModel):
    """Comparison dataset across registered campus devices."""

    total_devices: int
    devices: List[DeviceComparisonItem] = Field(default_factory=list)
    timestamp: datetime


# ============================================================================
# Phase 4 Topology Discovery Schemas (LLDP & CDP)
# ============================================================================


class TopologyLinkResponse(BaseModel):
    """Discovered link connection between local interface and remote neighbor."""

    id: int
    source_device_id: str
    local_interface: str
    remote_device_id: Optional[str] = None
    remote_chassis_id: str
    remote_chassis_id_subtype: Optional[str] = None
    remote_port_id: str
    remote_port_id_subtype: Optional[str] = None
    remote_port_desc: Optional[str] = None
    remote_system_name: Optional[str] = None
    remote_system_desc: Optional[str] = None
    protocol: str = Field(..., description="Discovery protocol ('lldp' or 'cdp')")
    discovered_at: datetime
    last_seen_at: datetime
    discovery_source: str = Field(..., description="Collection source ('snmp' or 'mock')")
    resolution_state: str = Field(..., description="Resolution status ('resolved' or 'unresolved')")
    link_status: str = Field(..., description="Link operational health ('active', 'stale', 'down')")
    is_mock: bool = Field(False, description="True if link was generated via mock topology provider")
    is_stale: bool = Field(False, description="True if link observation has not been refreshed recently")

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def compute_link_flags(self) -> "TopologyLinkResponse":
        self.is_mock = self.discovery_source == "mock"
        self.is_stale = self.link_status == "stale"
        return self


class TopologyLinkListResponse(BaseModel):
    """List of all discovered network topology links with summary counts."""

    total_links: int
    resolved_links: int
    unresolved_links: int
    stale_links: int
    links: List[TopologyLinkResponse] = Field(default_factory=list)
    timestamp: datetime


class DeviceNeighborsResponse(BaseModel):
    """Discovered neighbor connections for a specific device."""

    device_id: str
    device_name: Optional[str] = None
    total_neighbors: int
    neighbors: List[TopologyLinkResponse] = Field(default_factory=list)
    timestamp: datetime


class TopologyDiscoveryTriggerResponse(BaseModel):
    """Immediate outcome of initiating discovery against a target device."""

    device_id: str
    success: bool
    status: str = Field(..., description="Outcome: 'success', 'failed', 'unsupported', 'empty'")
    protocol_used: str = Field(..., description="'lldp', 'cdp', 'both', 'none'")
    neighbors_found: int = 0
    neighbors_resolved: int = 0
    message: str
    duration_ms: float = 0.0
    timestamp: datetime


class DeviceDiscoveryStatusResponse(BaseModel):
    """Current discovery state, protocol capabilities, and historical attempt info."""

    device_id: str
    status: str = Field("idle", description="'idle', 'in_progress', 'success', 'failed', 'unsupported', 'empty'")
    protocol: str = Field("lldp", description="Default configured protocol")
    lldp_supported: bool = False
    cdp_supported: bool = False
    discovered_neighbors_count: int = 0
    resolved_neighbors_count: int = 0
    last_discovery_at: Optional[datetime] = None
    last_discovery_duration_ms: Optional[float] = None
    last_error: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class UnresolvedNeighborsResponse(BaseModel):
    """Collection of discovered neighbors that do not match registered campus devices."""

    total_unresolved: int
    unresolved_neighbors: List[TopologyLinkResponse] = Field(default_factory=list)
    timestamp: datetime


# ============================================================================
# Phase 6: Topology Change Detection & Alerting Schemas
# ============================================================================


class AlertAcknowledgeRequest(BaseModel):
    """Payload to acknowledge an open topology alert."""

    acknowledged_by: Optional[str] = Field(
        "Network Operator",
        min_length=1,
        max_length=100,
        description="Operator or engineer ID",
    )
    note: Optional[str] = Field(None, max_length=500, description="Optional acknowledgement comment")


class AlertResolveRequest(BaseModel):
    """Payload to mark an alert as resolved."""

    resolved_by: Optional[str] = Field(
        "Network Operator",
        min_length=1,
        max_length=100,
        description="Operator or engineer ID",
    )
    note: Optional[str] = Field(None, max_length=500, description="Optional resolution comment")


class TopologyAlertResponse(BaseModel):
    """Detailed representation of a topology change event or operational alert."""

    id: str
    event_type: str
    severity: str
    status: str
    source_device_id: str
    source_device_name: Optional[str] = None
    remote_device_id: Optional[str] = None
    remote_device_name: Optional[str] = None
    remote_chassis_id: Optional[str] = None
    local_interface: Optional[str] = None
    remote_port_id: Optional[str] = None
    protocol: Optional[str] = None
    message: str
    details: Optional[str] = None
    first_detected_at: datetime
    last_seen_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    acknowledgement_note: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None
    occurrence_count: int = 1
    is_mock: bool = False
    discovery_source: str = "snmp"

    model_config = ConfigDict(from_attributes=True)


class TopologyAlertListResponse(BaseModel):
    """Paginated or filtered list of topology alerts."""

    total: int
    open_count: int
    acknowledged_count: int
    resolved_count: int
    alerts: List[TopologyAlertResponse] = Field(default_factory=list)
    timestamp: datetime


class TopologyAlertSummaryResponse(BaseModel):
    """High-level summary of topology alert counts by status, severity, and event type."""

    total_alerts: int
    open_alerts: int
    acknowledged_alerts: int
    resolved_alerts: int
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_event_type: Dict[str, int] = Field(default_factory=dict)
    mock_alerts_count: int = 0
    actual_alerts_count: int = 0
    timestamp: datetime





