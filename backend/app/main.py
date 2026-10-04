"""FastAPI application for Smart Network Monitoring AI.

Provides RESTful endpoints for network telemetry queries, history filtering,
and a WebSocket endpoint for real-time traffic metric streaming.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db, init_db
from app.models import (
    AnomalyEventModel,
    DeviceModel,
    NetworkMetricModel,
    ResearchDatasetModel,
    ResearchExperimentModel,
)
from app.schemas import (
    AnomalyEventResponse,
    AnomalyListResponse,
    AnomalySummaryResponse,
    CampusHierarchyResponse,
    CampusTelemetrySummaryResponse,
    CampusTimelineResponse,
    DeviceComparisonResponse,
    DeviceCreateRequest,
    DeviceHealthResponse,
    DeviceListResponse,
    DeviceMonitoringControlRequest,
    DeviceResponse,
    DeviceSummaryResponse,
    DeviceTelemetryHistoryResponse,
    DeviceTelemetryResponse,
    DeviceUpdateRequest,
    HealthResponse,
    HistoricalMetricsResponse,
    InterfaceListResponse,
    MonitoringControlRequest,
    MonitoringSummaryResponse,
    NetworkMetricResponse,
    ScenarioListResponse,
    ScenarioMetaResponse,
    SimulationResetResponse,
    SimulationResultResponse,
    SimulationRunRequest,
    DeviceDiscoveryStatusResponse,
    DeviceNeighborsResponse,
    TopologyDiscoveryTriggerResponse,
    TopologyLinkListResponse,
    TopologyLinkResponse,
    UnresolvedNeighborsResponse,
    AlertAcknowledgeRequest,
    AlertResolveRequest,
    TopologyAlertListResponse,
    TopologyAlertResponse,
    TopologyAlertSummaryResponse,
    ResearchDatasetResponse,
    ResearchDatasetListResponse,
    ResearchDatasetDetailResponse,
    ResearchExperimentRunRequest,
    ResearchExperimentResponse,
    ResearchExperimentListResponse,
    ResearchExperimentProgressResponse,
    PaperReferenceMetricResponse,
    ComparisonSummaryResponse,
    ConfusionMatrixResponse,
)
from app.services.alerting import alert_service
from app.services.devices import device_service
from app.services.monitoring import monitoring_service
from app.services.polling import polling_service
from app.services.simulation import simulation_service
from app.services.topology import topology_service
from app.services.research.dataset_service import (
    dataset_service,
    PRIMARY_FEATURES,
    DatasetValidationError,
)
from app.services.research.experiment_runner import experiment_runner
from app.services.research.reference_data import PUBLISHED_PAPER_RESULTS, PAPER_METADATA


# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("network_monitoring.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager handling database initialization and monitoring loop lifecycle."""
    logger.info("Starting up Smart Network Monitoring AI service...")
    init_db()

    # Pre-seed default benchmark sample dataset if not present
    try:
        sample_db = SessionLocal()
        dataset_service.ensure_default_sample_dataset(sample_db)
        sample_db.close()
    except Exception as exc:
        logger.warning("Could not auto-initialize sample dataset: %s", exc)

    # Connect remote device polling service broadcast to monitoring_service websocket broadcaster
    polling_service.broadcast_callback = monitoring_service.broadcast_event

    # Start background collector on the default active interface
    try:
        await monitoring_service.start()
    except Exception as exc:
        logger.error("Failed to start background monitoring on startup: %s", exc)

    # Start background remote device polling engine
    try:
        await polling_service.start()
    except Exception as exc:
        logger.error("Failed to start device polling engine on startup: %s", exc)

    yield

    logger.info("Shutting down Smart Network Monitoring AI service...")
    await polling_service.stop()
    await monitoring_service.stop()



app = FastAPI(
    title="Smart Network Monitoring AI",
    description=(
        "Production-grade network telemetry API collecting real-time host adapter statistics, "
        "providing SQLite-persisted history and live WebSocket streaming."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS configuration for future React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# REST API Endpoints (/api/v1)
# ============================================================================


@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    summary="Check API and database health",
    tags=["System"],
)
def get_health(db: Session = Depends(get_db)) -> HealthResponse:
    """Check connectivity to SQLite and status of the background monitoring loop."""
    db_status = "connected"
    overall_status = "ok"

    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        db_status = "error"
        overall_status = "degraded"

    monitor_status = "running" if monitoring_service._is_running else "stopped"

    return HealthResponse(
        status=overall_status,
        database=db_status,
        monitoring=monitor_status,
        active_interface=monitoring_service.active_interface,
        timestamp=datetime.now(timezone.utc),
    )


@app.get(
    "/api/v1/interfaces",
    response_model=InterfaceListResponse,
    summary="List available network interfaces",
    tags=["Interfaces"],
)
def get_interfaces() -> InterfaceListResponse:
    """Retrieve all physical and virtual network interfaces detected on the host machine."""
    try:
        interfaces = monitoring_service.get_available_interfaces()
        details = monitoring_service.get_interface_details()
        return InterfaceListResponse(
            interfaces=interfaces,
            details=details,
            active_interface=monitoring_service.active_interface,
            count=len(interfaces),
        )
    except Exception as exc:
        logger.error("Failed to query network interfaces: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to read host network interfaces: {exc}",
        )


@app.get(
    "/api/v1/metrics/current",
    response_model=NetworkMetricResponse,
    summary="Get current network metrics",
    tags=["Telemetry"],
)
def get_current_metrics() -> NetworkMetricResponse:
    """Fetch the latest actual telemetry sample collected from the active monitoring interface."""
    latest = monitoring_service.get_current_metric_response()
    if latest is None:
        # Fallback attempt: if monitoring is running but hasn't completed first tick, collect synchronously
        if monitoring_service.active_interface:
            try:
                sample = monitoring_service.collector.collect(monitoring_service.active_interface)
                return NetworkMetricResponse(
                    id=None,
                    timestamp=datetime.fromtimestamp(sample.timestamp, tz=timezone.utc),
                    interface=sample.interface_name,
                    upload_mbps=sample.upload_mbps,
                    download_mbps=sample.download_mbps,
                    packets_sent_per_sec=sample.packets_sent_per_sec,
                    packets_received_per_sec=sample.packets_recv_per_sec,
                    cumulative_sent_mb=round(sample.cumulative_bytes_sent / (1024 * 1024), 2),
                    cumulative_received_mb=round(sample.cumulative_bytes_recv / (1024 * 1024), 2),
                    session_transferred_mb=sample.session_transferred_mb,
                    is_initial_sample=sample.is_initial_sample,
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Collector error reading interface: {exc}",
                )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No telemetry samples collected yet. Please ensure monitoring is active.",
        )

    return latest


@app.get(
    "/api/v1/metrics/history",
    response_model=HistoricalMetricsResponse,
    summary="Query historical network metrics",
    tags=["Telemetry"],
)
def get_metrics_history(
    interface: Optional[str] = Query(None, description="Filter metrics by network interface name"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of historical records to return (1-1000)"),
    start_time: Optional[datetime] = Query(None, description="Start UTC timestamp filter in ISO 8601 format"),
    end_time: Optional[datetime] = Query(None, description="End UTC timestamp filter in ISO 8601 format"),
    db: Session = Depends(get_db),
) -> HistoricalMetricsResponse:
    """Retrieve persisted historical network telemetry records with filtering and pagination."""
    if start_time and end_time and start_time > end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must be earlier than or equal to end_time.",
        )

    query = db.query(NetworkMetricModel)

    if interface:
        query = query.filter(NetworkMetricModel.interface == interface)
    if start_time:
        query = query.filter(NetworkMetricModel.timestamp >= start_time)
    if end_time:
        query = query.filter(NetworkMetricModel.timestamp <= end_time)

    records = query.order_by(NetworkMetricModel.timestamp.desc()).limit(limit).all()

    metric_responses = [
        NetworkMetricResponse(
            id=r.id,
            timestamp=r.timestamp,
            interface=r.interface,
            upload_mbps=r.upload_mbps,
            download_mbps=r.download_mbps,
            packets_sent_per_sec=r.packets_sent_per_sec,
            packets_received_per_sec=r.packets_received_per_sec,
            cumulative_sent_mb=r.cumulative_sent_mb,
            cumulative_received_mb=r.cumulative_received_mb,
            session_transferred_mb=r.session_transferred_mb,
            is_initial_sample=False,
        )
        for r in records
    ]

    return HistoricalMetricsResponse(
        interface=interface,
        total_returned=len(metric_responses),
        limit=limit,
        metrics=metric_responses,
    )


@app.get(
    "/api/v1/summary",
    response_model=MonitoringSummaryResponse,
    summary="Get monitoring session summary",
    tags=["Telemetry"],
)
def get_monitoring_summary(db: Session = Depends(get_db)) -> MonitoringSummaryResponse:
    """Fetch session overview including peaks, session data volume, and total stored records."""
    return monitoring_service.get_summary(db)


@app.post(
    "/api/v1/monitoring/start",
    summary="Start or reconfigure background monitoring",
    tags=["Control"],
)
async def start_monitoring(
    payload: Optional[MonitoringControlRequest] = None,
) -> dict:
    """Start or update the background monitoring loop for a specified interface and interval."""
    iface = payload.interface if payload else None
    interval = payload.interval_seconds if payload else 1.0

    if iface:
        available = monitoring_service.get_available_interfaces()
        if iface not in available:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interface '{iface}' not found. Available: {available}",
            )

    await monitoring_service.start(interface=iface, interval=interval)
    return {
        "status": "success",
        "message": f"Monitoring started for interface '{monitoring_service.active_interface}'",
        "interface": monitoring_service.active_interface,
        "interval_seconds": monitoring_service.interval_seconds,
    }


@app.post(
    "/api/v1/monitoring/stop",
    summary="Stop background monitoring",
    tags=["Control"],
)
async def stop_monitoring() -> dict:
    """Gracefully stop the background monitoring loop."""
    await monitoring_service.stop()
    return {
        "status": "success",
        "message": "Monitoring stopped",
    }


# ============================================================================
# Anomaly Detection Endpoints (/api/v1/anomalies)
# ============================================================================


@app.get(
    "/api/v1/anomalies",
    response_model=AnomalyListResponse,
    summary="Query detected network anomaly events",
    tags=["Anomaly Detection"],
)
def get_anomalies(
    limit: int = Query(50, ge=1, le=500, description="Maximum number of anomaly events to return (1-500)"),
    interface: Optional[str] = Query(None, description="Filter by network interface"),
    severity: Optional[str] = Query(None, description="Filter by severity ('Unusual Traffic', 'High Anomaly')"),
    start_time: Optional[datetime] = Query(None, description="Start UTC timestamp filter in ISO 8601 format"),
    end_time: Optional[datetime] = Query(None, description="End UTC timestamp filter in ISO 8601 format"),
    db: Session = Depends(get_db),
) -> AnomalyListResponse:
    """Retrieve persisted network anomaly events with filtering and pagination."""
    if start_time and end_time and start_time > end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must be earlier than or equal to end_time.",
        )

    query = db.query(AnomalyEventModel)
    if interface:
        query = query.filter(AnomalyEventModel.interface == interface)
    if severity:
        query = query.filter(AnomalyEventModel.severity == severity)
    if start_time:
        query = query.filter(AnomalyEventModel.timestamp >= start_time)
    if end_time:
        query = query.filter(AnomalyEventModel.timestamp <= end_time)

    records = query.order_by(AnomalyEventModel.timestamp.desc()).limit(limit).all()

    event_responses = [
        AnomalyEventResponse(
            id=r.id,
            timestamp=r.timestamp,
            interface=r.interface,
            anomaly_score=r.anomaly_score,
            severity=r.severity,
            detection_method=r.detection_method,
            metrics_snapshot=r.metrics_snapshot,
            explanation=r.explanation,
        )
        for r in records
    ]

    return AnomalyListResponse(
        total_returned=len(event_responses),
        limit=limit,
        events=event_responses,
    )


@app.get(
    "/api/v1/anomalies/latest",
    response_model=Optional[AnomalyEventResponse],
    summary="Get most recent network anomaly event",
    tags=["Anomaly Detection"],
)
def get_latest_anomaly(
    interface: Optional[str] = Query(None, description="Filter by network interface"),
    db: Session = Depends(get_db),
) -> Optional[AnomalyEventResponse]:
    """Retrieve the most recent detected anomaly event, or null if no anomalies have occurred."""
    query = db.query(AnomalyEventModel)
    if interface:
        query = query.filter(AnomalyEventModel.interface == interface)

    record = query.order_by(AnomalyEventModel.timestamp.desc()).first()
    if not record:
        return None

    return AnomalyEventResponse(
        id=record.id,
        timestamp=record.timestamp,
        interface=record.interface,
        anomaly_score=record.anomaly_score,
        severity=record.severity,
        detection_method=record.detection_method,
        metrics_snapshot=record.metrics_snapshot,
        explanation=record.explanation,
    )


@app.get(
    "/api/v1/anomalies/summary",
    response_model=AnomalySummaryResponse,
    summary="Get anomaly detection engine summary",
    tags=["Anomaly Detection"],
)
def get_anomaly_summary(db: Session = Depends(get_db)) -> AnomalySummaryResponse:
    """Fetch anomaly detection engine status, training state, and event counters."""
    return monitoring_service.get_anomaly_summary(db)


# ============================================================================
# Simulation Lab Endpoints (/api/v1/simulation)
# ============================================================================


@app.get(
    "/api/v1/simulation/scenarios",
    response_model=ScenarioListResponse,
    summary="List available simulation scenarios",
    tags=["Simulation Lab"],
)
def get_simulation_scenarios() -> ScenarioListResponse:
    """Retrieve all pre-configured synthetic telemetry scenarios and metadata."""
    scenarios = simulation_service.list_scenarios()
    return ScenarioListResponse(
        scenarios=[ScenarioMetaResponse(**s) for s in scenarios],
        count=len(scenarios),
    )


@app.post(
    "/api/v1/simulation/run",
    response_model=SimulationResultResponse,
    summary="Execute controlled simulation run",
    tags=["Simulation Lab"],
)
def run_simulation(request: SimulationRunRequest) -> SimulationResultResponse:
    """Run a controlled simulation scenario against an isolated AnomalyDetector instance.

    Guarantees full isolation from production host network telemetry and the SQLite store.
    Does not modify real network adapters or live WebSocket streams.
    """
    try:
        result = simulation_service.run_simulation(
            scenario_id=request.scenario_id,
            seed=request.seed if request.seed is not None else 42,
        )
        return SimulationResultResponse(**result.to_dict())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Simulation run failure: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation execution error: {exc}",
        )


@app.get(
    "/api/v1/simulation/results",
    response_model=SimulationResultResponse,
    summary="Get latest simulation validation result",
    tags=["Simulation Lab"],
)
def get_simulation_results() -> SimulationResultResponse:
    """Retrieve the most recently completed simulation validation result."""
    result = simulation_service.get_latest_result()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No simulation runs found. Please run a simulation first.",
        )
    return SimulationResultResponse(**result.to_dict())


@app.post(
    "/api/v1/simulation/reset",
    response_model=SimulationResetResponse,
    summary="Reset simulation state",
    tags=["Simulation Lab"],
)
def reset_simulation() -> SimulationResetResponse:
    """Clear cached simulation validation results."""
    simulation_service.reset()
    return SimulationResetResponse(
        status="ok",
        message="Simulation state and cached results cleared successfully.",
    )


# ============================================================================
# Campus Multi-Device Registry Endpoints (/api/v1/devices)
# ============================================================================


@app.get(
    "/api/v1/devices",
    response_model=DeviceListResponse,
    summary="List registered campus network devices",
    tags=["Device Registry"],
)
def get_devices(
    device_type: Optional[str] = Query(None, description="Filter by device type (router, switch, access_point, server, host, other)"),
    department: Optional[str] = Query(None, description="Filter by department"),
    building: Optional[str] = Query(None, description="Filter by building"),
    floor: Optional[str] = Query(None, description="Filter by floor"),
    monitoring_status: Optional[str] = Query(None, description="Filter by monitoring status (active, inactive, maintenance)"),
    connection_status: Optional[str] = Query(None, description="Filter by connection status (online, offline, unknown)"),
    search: Optional[str] = Query(None, description="Search by name, IP, department, building, vendor/model, or location"),
    db: Session = Depends(get_db),
) -> DeviceListResponse:
    """Query all registered campus network devices with optional categorization and location filters."""
    devices = device_service.list_devices(
        db=db,
        device_type=device_type,
        department=department,
        building=building,
        floor=floor,
        monitoring_status=monitoring_status,
        connection_status=connection_status,
        search=search,
    )
    return DeviceListResponse(
        total=len(devices),
        devices=[DeviceResponse.model_validate(d) for d in devices],
    )


@app.get(
    "/api/v1/devices/summary",
    response_model=DeviceSummaryResponse,
    summary="Get campus device inventory summary",
    tags=["Device Registry"],
)
def get_device_summary(db: Session = Depends(get_db)) -> DeviceSummaryResponse:
    """Compute aggregate device counts by operational status, category, and department."""
    return device_service.get_summary(db=db)


@app.get(
    "/api/v1/devices/telemetry/summary",
    response_model=CampusTelemetrySummaryResponse,
    summary="Get campus-wide remote device telemetry aggregate summary",
    tags=["Device Telemetry"],
)
def get_campus_telemetry_summary(db: Session = Depends(get_db)) -> CampusTelemetrySummaryResponse:
    """Compute aggregate telemetry throughput, reachability breakdown, and error totals across campus devices."""
    return device_service.get_campus_telemetry_summary(db=db)


@app.get(
    "/api/v1/devices/hierarchy",
    response_model=CampusHierarchyResponse,
    summary="Get campus topological hierarchy (Campus -> Building -> Floor -> Department -> Device)",
    tags=["Device Registry"],
)
def get_campus_hierarchy(db: Session = Depends(get_db)) -> CampusHierarchyResponse:
    """Retrieve full logical hierarchy of campus infrastructure with device health status."""
    return device_service.get_campus_hierarchy(db=db)


@app.get(
    "/api/v1/devices/telemetry/timeline",
    response_model=CampusTimelineResponse,
    summary="Get campus-wide aggregate throughput timeline",
    tags=["Device Telemetry"],
)
def get_campus_telemetry_timeline(
    hours: int = Query(1, ge=1, le=168, description="Time window in hours (1-168)"),
    db: Session = Depends(get_db),
) -> CampusTimelineResponse:
    """Retrieve chronological aggregate upload and download throughput across all reporting campus devices."""
    return device_service.get_campus_timeline(db=db, hours=hours)


@app.get(
    "/api/v1/devices/telemetry/comparison",
    response_model=DeviceComparisonResponse,
    summary="Compare metric telemetry across all registered campus devices",
    tags=["Device Telemetry"],
)
def get_device_comparison(db: Session = Depends(get_db)) -> DeviceComparisonResponse:
    """Retrieve latest metric rates, error counters, and reliable operational status for all registered devices."""
    return device_service.get_device_comparison(db=db)


@app.post(
    "/api/v1/devices",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new campus network device",
    tags=["Device Registry"],
)
def create_device(
    payload: DeviceCreateRequest,
    db: Session = Depends(get_db),
) -> DeviceResponse:
    """Register an authorized campus router, switch, AP, server, or host in the monitoring inventory."""
    device = device_service.create_device(db=db, req=payload)
    return DeviceResponse.model_validate(device)


@app.get(
    "/api/v1/devices/{device_id}",
    response_model=DeviceResponse,
    summary="Get details of a specific device",
    tags=["Device Registry"],
)
def get_device_by_id(
    device_id: str,
    db: Session = Depends(get_db),
) -> DeviceResponse:
    """Retrieve full configuration and status details for a single registered device."""
    device = device_service.get_device(db=db, device_id=device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID '{device_id}' not found.",
        )
    return DeviceResponse.model_validate(device)


@app.patch(
    "/api/v1/devices/{device_id}",
    response_model=DeviceResponse,
    summary="Update a registered campus device",
    tags=["Device Registry"],
)
def update_device(
    device_id: str,
    payload: DeviceUpdateRequest,
    db: Session = Depends(get_db),
) -> DeviceResponse:
    """Partially update device configuration, location, or monitoring status."""
    updated = device_service.update_device(db=db, device_id=device_id, req=payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID '{device_id}' not found.",
        )
    return DeviceResponse.model_validate(updated)


@app.delete(
    "/api/v1/devices/{device_id}",
    summary="Delete a registered campus device",
    tags=["Device Registry"],
)
def delete_device(
    device_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Remove a device record from the campus registry."""
    deleted = device_service.delete_device(db=db, device_id=device_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID '{device_id}' not found.",
        )
    return {
        "status": "success",
        "message": f"Device '{device_id}' deleted successfully.",
        "device_id": device_id,
    }


@app.get(
    "/api/v1/devices/{device_id}/telemetry/latest",
    response_model=DeviceTelemetryResponse,
    summary="Get most recent telemetry sample for a device",
    tags=["Device Telemetry"],
)
def get_device_latest_telemetry(
    device_id: str,
    interface: Optional[str] = Query(None, description="Optional interface name filter"),
    db: Session = Depends(get_db),
) -> DeviceTelemetryResponse:
    """Retrieve the latest telemetry measurement recorded for a specific remote campus device."""
    device = device_service.get_device(db=db, device_id=device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID '{device_id}' not found.",
        )
    latest = device_service.get_latest_telemetry(db=db, device_id=device_id, interface_name=interface)
    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No telemetry samples collected yet for device '{device_id}'.",
        )
    return DeviceTelemetryResponse.model_validate(latest)


@app.get(
    "/api/v1/devices/{device_id}/telemetry/history",
    response_model=DeviceTelemetryHistoryResponse,
    summary="Query historical telemetry for a remote device",
    tags=["Device Telemetry"],
)
def get_device_telemetry_history(
    device_id: str,
    interface: Optional[str] = Query(None, description="Optional interface name filter"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of historical records to return (1-500)"),
    start_time: Optional[datetime] = Query(None, description="Start UTC timestamp filter in ISO 8601 format"),
    end_time: Optional[datetime] = Query(None, description="End UTC timestamp filter in ISO 8601 format"),
    db: Session = Depends(get_db),
) -> DeviceTelemetryHistoryResponse:
    """Retrieve bounded historical telemetry records for a registered campus device."""
    device = device_service.get_device(db=db, device_id=device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID '{device_id}' not found.",
        )
    if start_time and end_time and start_time > end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must be earlier than or equal to end_time.",
        )
    records = device_service.get_telemetry_history(
        db=db,
        device_id=device_id,
        limit=limit,
        interface_name=interface,
        start_time=start_time,
        end_time=end_time,
    )
    return DeviceTelemetryHistoryResponse(
        device_id=device_id,
        interface_name=interface,
        total_returned=len(records),
        limit=limit,
        telemetry=[DeviceTelemetryResponse.model_validate(r) for r in records],
    )


@app.get(
    "/api/v1/devices/{device_id}/health",
    response_model=DeviceHealthResponse,
    summary="Get reachability, polling status, and health for a device",
    tags=["Device Telemetry"],
)
def get_device_health(
    device_id: str,
    db: Session = Depends(get_db),
) -> DeviceHealthResponse:
    """Retrieve reachability state, last poll timestamp, error messages, and monitoring configuration."""
    device = device_service.get_device(db=db, device_id=device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID '{device_id}' not found.",
        )
    return DeviceHealthResponse(
        device_id=device.id,
        name=device.name,
        ip_address=device.ip_address,
        reachability=device.reachability,
        polling_enabled=device.polling_enabled,
        polling_interval_seconds=device.polling_interval_seconds,
        last_poll_at=device.last_poll_at,
        last_poll_status=device.last_poll_status,
        last_poll_error=device.last_poll_error,
        timestamp=datetime.now(timezone.utc),
    )


@app.post(
    "/api/v1/devices/{device_id}/monitoring/start",
    response_model=DeviceResponse,
    summary="Enable active remote polling for a registered device",
    tags=["Device Telemetry"],
)
async def start_device_monitoring(
    device_id: str,
    payload: Optional[DeviceMonitoringControlRequest] = None,
    db: Session = Depends(get_db),
) -> DeviceResponse:
    """Explicitly enable periodic polling for a registered campus device and trigger an initial poll."""
    device = device_service.get_device(db=db, device_id=device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID '{device_id}' not found.",
        )
    interval = payload.interval_seconds if payload else None
    updated = polling_service.enable_polling(db=db, device_id=device_id, interval_seconds=interval)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID '{device_id}' not found.",
        )
    # Trigger an immediate background poll attempt
    asyncio.create_task(polling_service.poll_device_job(device_id))
    return DeviceResponse.model_validate(updated)


@app.post(
    "/api/v1/devices/{device_id}/monitoring/stop",
    response_model=DeviceResponse,
    summary="Disable active remote polling for a device",
    tags=["Device Telemetry"],
)
def stop_device_monitoring(
    device_id: str,
    db: Session = Depends(get_db),
) -> DeviceResponse:
    """Disable periodic remote polling for a device."""
    device = device_service.get_device(db=db, device_id=device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID '{device_id}' not found.",
        )
    updated = polling_service.disable_polling(db=db, device_id=device_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID '{device_id}' not found.",
        )
    return DeviceResponse.model_validate(updated)


# ============================================================================
# Phase 4: Topology Discovery Endpoints
# ============================================================================


@app.get(
    "/api/v1/topology/links",
    response_model=TopologyLinkListResponse,
    summary="Retrieve discovered network topology links",
    tags=["Network Topology"],
)
def get_topology_links(
    source_device_id: Optional[str] = Query(None, description="Filter links by source device ID"),
    protocol: Optional[str] = Query(None, description="Filter by discovery protocol ('lldp', 'cdp')"),
    link_status: Optional[str] = Query(None, description="Filter by operational status ('active', 'stale', 'down')"),
    resolution_state: Optional[str] = Query(None, description="Filter by resolution ('resolved', 'unresolved')"),
    limit: int = Query(100, ge=1, le=500, description="Maximum links to return"),
    db: Session = Depends(get_db),
) -> TopologyLinkListResponse:
    """Fetch discovered physical or logical links with optional resolution and status filters."""
    links = topology_service.get_links(
        db=db,
        source_device_id=source_device_id,
        protocol=protocol,
        link_status=link_status,
        resolution_state=resolution_state,
        limit=limit,
    )
    total = len(links)
    resolved = sum(1 for l in links if l.resolution_state == "resolved")
    unresolved = sum(1 for l in links if l.resolution_state == "unresolved")
    stale = sum(1 for l in links if l.link_status == "stale")

    return TopologyLinkListResponse(
        total_links=total,
        resolved_links=resolved,
        unresolved_links=unresolved,
        stale_links=stale,
        links=[TopologyLinkResponse.model_validate(l) for l in links],
        timestamp=datetime.now(timezone.utc),
    )


@app.get(
    "/api/v1/topology/unresolved",
    response_model=UnresolvedNeighborsResponse,
    summary="Retrieve all discovered neighbors that are not registered campus devices",
    tags=["Network Topology"],
)
def get_unresolved_neighbors(
    db: Session = Depends(get_db),
) -> UnresolvedNeighborsResponse:
    """Retrieve external or unregistered neighbor records discovered via LLDP/CDP."""
    unresolved = topology_service.get_unresolved_neighbors(db=db)
    return UnresolvedNeighborsResponse(
        total_unresolved=len(unresolved),
        unresolved_neighbors=[TopologyLinkResponse.model_validate(u) for u in unresolved],
        timestamp=datetime.now(timezone.utc),
    )


@app.post(
    "/api/v1/topology/devices/{device_id}/discover",
    response_model=TopologyDiscoveryTriggerResponse,
    summary="Trigger authorized read-only topology discovery for a registered device",
    tags=["Network Topology"],
)
def discover_device_topology(
    device_id: str,
    db: Session = Depends(get_db),
) -> TopologyDiscoveryTriggerResponse:
    """Initiate a read-only LLDP/CDP topology query against a registered campus device."""
    device = device_service.get_device(db=db, device_id=device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID '{device_id}' not found.",
        )

    result = topology_service.discover_device(db=db, device_id=device_id)
    resolved_count = result.resolved_neighbors_count

    msg = (
        f"Discovery completed with status '{result.status}'. Found {len(result.neighbors)} neighbors ({resolved_count} resolved)."
        if result.success or result.status in ("empty", "unsupported")
        else (result.error_message or "Discovery failed.")
    )

    return TopologyDiscoveryTriggerResponse(
        device_id=device_id,
        success=result.success,
        status=result.status,
        protocol_used=result.protocol_used,
        neighbors_found=len(result.neighbors),
        neighbors_resolved=resolved_count,
        message=msg,
        duration_ms=result.duration_ms,
        timestamp=datetime.now(timezone.utc),
    )


@app.get(
    "/api/v1/topology/devices/{device_id}/neighbors",
    response_model=DeviceNeighborsResponse,
    summary="Retrieve discovered neighbors for a specific device",
    tags=["Network Topology"],
)
def get_device_neighbors(
    device_id: str,
    db: Session = Depends(get_db),
) -> DeviceNeighborsResponse:
    """Retrieve all link connections originating from or connected to a given campus device."""
    device = device_service.get_device(db=db, device_id=device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID '{device_id}' not found.",
        )
    neighbors = topology_service.get_device_neighbors(db=db, device_id=device_id)
    return DeviceNeighborsResponse(
        device_id=device_id,
        device_name=device.name,
        total_neighbors=len(neighbors),
        neighbors=[TopologyLinkResponse.model_validate(n) for n in neighbors],
        timestamp=datetime.now(timezone.utc),
    )


@app.get(
    "/api/v1/topology/devices/{device_id}/status",
    response_model=DeviceDiscoveryStatusResponse,
    summary="Retrieve discovery execution status and protocol support for a device",
    tags=["Network Topology"],
)
def get_device_discovery_status(
    device_id: str,
    db: Session = Depends(get_db),
) -> DeviceDiscoveryStatusResponse:
    """Retrieve current discovery state, protocol capabilities, and last execution results for a device."""
    device = device_service.get_device(db=db, device_id=device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID '{device_id}' not found.",
        )
    status_rec = topology_service.get_discovery_status(db=db, device_id=device_id)
    if not status_rec:
        return DeviceDiscoveryStatusResponse(
            device_id=device_id,
            status="idle",
            protocol="lldp",
            lldp_supported=False,
            cdp_supported=False,
            discovered_neighbors_count=0,
            resolved_neighbors_count=0,
            last_discovery_at=None,
            last_discovery_duration_ms=None,
            last_error=None,
            timestamp=datetime.now(timezone.utc),
        )
    return DeviceDiscoveryStatusResponse(
        device_id=status_rec.device_id,
        status=status_rec.status,
        protocol=status_rec.protocol or "lldp",
        lldp_supported=status_rec.lldp_supported,
        cdp_supported=status_rec.cdp_supported,
        discovered_neighbors_count=status_rec.discovered_neighbors_count,
        resolved_neighbors_count=status_rec.resolved_neighbors_count,
        last_discovery_at=status_rec.last_discovery_at,
        last_discovery_duration_ms=status_rec.last_discovery_duration_ms,
        last_error=status_rec.last_error,
        timestamp=datetime.now(timezone.utc),
    )


# ============================================================================
# Phase 6: Topology Change Detection & Alerting Endpoints
# ============================================================================


@app.get(
    "/api/v1/alerts",
    response_model=TopologyAlertListResponse,
    summary="List topology change detection alerts with filtering",
    tags=["Topology Alerts"],
)
def get_topology_alerts(
    status: Optional[str] = Query(None, description="Filter by status: open, acknowledged, resolved, or all"),
    severity: Optional[str] = Query(None, description="Filter by severity: info, warning, critical, error"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    device_id: Optional[str] = Query(None, description="Filter by source or remote device ID"),
    is_mock: Optional[bool] = Query(None, description="Filter by mock vs. actual SNMP alerts"),
    limit: int = Query(50, ge=1, le=500, description="Max alerts to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
) -> TopologyAlertListResponse:
    """Retrieve layer-2 topology change detection events and operational alerts."""
    alerts = alert_service.get_alerts(
        db=db,
        status=status,
        severity=severity,
        event_type=event_type,
        device_id=device_id,
        is_mock=is_mock,
        limit=limit,
        offset=offset,
    )
    summary = alert_service.get_alert_summary(db=db)

    return TopologyAlertListResponse(
        total=summary["total_alerts"],
        open_count=summary["open_alerts"],
        acknowledged_count=summary["acknowledged_alerts"],
        resolved_count=summary["resolved_alerts"],
        alerts=[TopologyAlertResponse.model_validate(a) for a in alerts],
        timestamp=datetime.now(timezone.utc),
    )


@app.get(
    "/api/v1/alerts/summary",
    response_model=TopologyAlertSummaryResponse,
    summary="Retrieve high-level summary of topology alert counts",
    tags=["Topology Alerts"],
)
def get_topology_alerts_summary(
    db: Session = Depends(get_db),
) -> TopologyAlertSummaryResponse:
    """Retrieve aggregate counts of topology alerts by status, severity, and event type."""
    summary_data = alert_service.get_alert_summary(db=db)
    return TopologyAlertSummaryResponse(**summary_data)


@app.get(
    "/api/v1/alerts/{alert_id}",
    response_model=TopologyAlertResponse,
    summary="Retrieve details for a specific topology alert",
    tags=["Topology Alerts"],
)
def get_topology_alert_detail(
    alert_id: str,
    db: Session = Depends(get_db),
) -> TopologyAlertResponse:
    """Fetch complete metadata, interface mappings, and history for a single alert."""
    alert = alert_service.get_alert_by_id(db=db, alert_id=alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topology alert with ID '{alert_id}' not found.",
        )
    return TopologyAlertResponse.model_validate(alert)


@app.post(
    "/api/v1/alerts/{alert_id}/acknowledge",
    response_model=TopologyAlertResponse,
    summary="Acknowledge an open topology alert",
    tags=["Topology Alerts"],
)
def acknowledge_topology_alert(
    alert_id: str,
    payload: AlertAcknowledgeRequest,
    db: Session = Depends(get_db),
) -> TopologyAlertResponse:
    """Transition an active topology alert to acknowledged status."""
    try:
        alert = alert_service.acknowledge_alert(
            db=db,
            alert_id=alert_id,
            acknowledged_by=payload.acknowledged_by or "Network Operator",
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topology alert with ID '{alert_id}' not found.",
        )
    return TopologyAlertResponse.model_validate(alert)


@app.post(
    "/api/v1/alerts/{alert_id}/resolve",
    response_model=TopologyAlertResponse,
    summary="Resolve a topology alert",
    tags=["Topology Alerts"],
)
def resolve_topology_alert(
    alert_id: str,
    payload: AlertResolveRequest,
    db: Session = Depends(get_db),
) -> TopologyAlertResponse:
    """Transition a topology alert to resolved status."""
    try:
        alert = alert_service.resolve_alert(
            db=db,
            alert_id=alert_id,
            resolved_by=payload.resolved_by or "Network Operator",
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topology alert with ID '{alert_id}' not found.",
        )
    return TopologyAlertResponse.model_validate(alert)


# ============================================================================
# WebSocket Endpoint (/ws/metrics)
# ============================================================================



@app.websocket("/ws/metrics")
async def websocket_metrics_endpoint(websocket: WebSocket) -> None:
    """Stream live network metrics to connected clients using the shared monitoring service."""
    await monitoring_service.connect_websocket(websocket)
    try:
        while True:
            # Keep connection open and receive any incoming ping/control messages
            message = await websocket.receive_text()
            logger.debug("Received client message on /ws/metrics: %s", message)
    except WebSocketDisconnect:
        monitoring_service.disconnect_websocket(websocket)
    except Exception as exc:
        logger.warning("WebSocket connection exception: %s", exc)
        monitoring_service.disconnect_websocket(websocket)


# ============================================================================
# Research Paper & Experiment API Endpoints (/api/v1/research)
# ============================================================================


@app.get(
    "/api/v1/research/datasets",
    response_model=ResearchDatasetListResponse,
    summary="List registered flow datasets",
    tags=["Research - Datasets"],
)
def list_research_datasets(db: Session = Depends(get_db)) -> ResearchDatasetListResponse:
    """Retrieve all available NetFlow datasets available for research experiments."""
    datasets = db.query(ResearchDatasetModel).order_by(ResearchDatasetModel.created_at.desc()).all()
    results = []
    for d in datasets:
        features = json.loads(d.features_json) if d.features_json else []
        results.append(
            ResearchDatasetResponse(
                id=d.id,
                name=d.name,
                version=d.version,
                description=d.description,
                file_size_bytes=d.file_size_bytes,
                total_flows=d.total_flows,
                benign_flows=d.benign_flows,
                attack_flows=d.attack_flows,
                features=features,
                schema_type=d.schema_type or "native_netflow",
                is_adapted=bool(d.is_adapted),
                adaptation_notes=d.adaptation_notes,
                is_sample=d.is_sample,
                created_at=d.created_at,
            )
        )
    return ResearchDatasetListResponse(datasets=results, count=len(results))


@app.post(
    "/api/v1/research/datasets/upload",
    response_model=ResearchDatasetResponse,
    summary="Upload a new NetFlow CSV dataset",
    tags=["Research - Datasets"],
)
async def upload_research_dataset(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    version: str = Form("NF-UNSW-NB15"),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
) -> ResearchDatasetResponse:
    """Upload and validate a NetFlow dataset file (e.g., NF-UNSW-NB15 or UNSW-NB15 adapter)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename.")

    # Save to disk
    dataset_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix or ".csv"
    save_filename = f"{dataset_id}_{file.filename}"
    save_path = dataset_service.data_dir / save_filename

    try:
        with open(save_path, "wb") as f_out:
            shutil.copyfileobj(file.file, f_out)
    except Exception as exc:
        logger.error("Failed to save uploaded file: %s", exc)
        raise HTTPException(status_code=500, detail=f"File save error: {exc}")

    # Inspect and validate schema strictly
    try:
        stats = dataset_service.inspect_dataset_file(str(save_path))
    except (DatasetValidationError, Exception) as exc:
        if save_path.exists():
            save_path.unlink()
        logger.warning("Dataset validation rejected upload: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))

    display_name = name or Path(file.filename).stem
    dataset_model = dataset_service.register_dataset(
        db=db,
        name=display_name,
        version=version,
        file_path=str(save_path),
        description=description,
        is_sample=False,
    )

    return ResearchDatasetResponse(
        id=dataset_model.id,
        name=dataset_model.name,
        version=dataset_model.version,
        description=dataset_model.description,
        file_size_bytes=dataset_model.file_size_bytes,
        total_flows=dataset_model.total_flows,
        benign_flows=dataset_model.benign_flows,
        attack_flows=dataset_model.attack_flows,
        features=json.loads(dataset_model.features_json),
        schema_type=dataset_model.schema_type,
        is_adapted=dataset_model.is_adapted,
        adaptation_notes=dataset_model.adaptation_notes,
        is_sample=dataset_model.is_sample,
        created_at=dataset_model.created_at,
    )


@app.post(
    "/api/v1/research/datasets/sample",
    response_model=ResearchDatasetResponse,
    summary="Ensure or load bundled benchmark sample dataset",
    tags=["Research - Datasets"],
)
def load_sample_dataset(db: Session = Depends(get_db)) -> ResearchDatasetResponse:
    """Ensure the bundled 5,000-flow NF-UNSW-NB15 sample dataset is ready for instant verification."""
    model = dataset_service.ensure_default_sample_dataset(db)
    return ResearchDatasetResponse(
        id=model.id,
        name=model.name,
        version=model.version,
        description=model.description,
        file_size_bytes=model.file_size_bytes,
        total_flows=model.total_flows,
        benign_flows=model.benign_flows,
        attack_flows=model.attack_flows,
        features=json.loads(model.features_json),
        schema_type=model.schema_type,
        is_adapted=model.is_adapted,
        adaptation_notes=model.adaptation_notes,
        is_sample=model.is_sample,
        created_at=model.created_at,
    )


@app.get(
    "/api/v1/research/datasets/{dataset_id}",
    response_model=ResearchDatasetDetailResponse,
    summary="Get dataset details, sample preview, and schema validation",
    tags=["Research - Datasets"],
)
def get_dataset_details(dataset_id: str, db: Session = Depends(get_db)) -> ResearchDatasetDetailResponse:
    """Inspect dataset columns, sample rows, and paper feature coverage."""
    model = db.query(ResearchDatasetModel).filter(ResearchDatasetModel.id == dataset_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Dataset not found")

    stats = dataset_service.inspect_dataset_file(model.file_path)

    ds_resp = ResearchDatasetResponse(
        id=model.id,
        name=model.name,
        version=model.version,
        description=model.description,
        file_size_bytes=model.file_size_bytes,
        total_flows=model.total_flows,
        benign_flows=model.benign_flows,
        attack_flows=model.attack_flows,
        features=json.loads(model.features_json),
        schema_type=model.schema_type,
        is_adapted=model.is_adapted,
        adaptation_notes=model.adaptation_notes,
        is_sample=model.is_sample,
        created_at=model.created_at,
    )

    return ResearchDatasetDetailResponse(
        dataset=ds_resp,
        sample_rows=stats.get("sample_rows", []),
        validation={
            "detected_features": stats.get("detected_features", []),
            "missing_features": stats.get("missing_features", []),
            "has_label_column": stats.get("has_label_column", False),
            "is_paper_compliant": stats.get("is_paper_compliant", False),
            "expected_paper_features": PRIMARY_FEATURES,
            "schema_type": stats.get("schema_type", "native_netflow"),
            "is_adapted": stats.get("is_adapted", False),
            "adaptation_notes": stats.get("adaptation_notes"),
            "duration_unit": stats.get("duration_unit", "milliseconds"),
            "validation_status": stats.get("validation_status", "Valid"),
            "invalid_ip_rows": stats.get("invalid_ip_rows", 0),
            "malformed_rows": stats.get("malformed_rows", 0),
        },
    )


@app.delete(
    "/api/v1/research/datasets/{dataset_id}",
    summary="Delete a research dataset",
    tags=["Research - Datasets"],
)
def delete_research_dataset(dataset_id: str, db: Session = Depends(get_db)):
    """Delete a dataset and remove its physical file from disk."""
    model = db.query(ResearchDatasetModel).filter(ResearchDatasetModel.id == dataset_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # If file exists and not sample, remove file
    if not model.is_sample:
        p = Path(model.file_path)
        if p.exists():
            p.unlink()

    db.delete(model)
    db.commit()
    return {"status": "ok", "message": f"Dataset '{model.name}' removed successfully."}


@app.get(
    "/api/v1/research/experiments",
    response_model=ResearchExperimentListResponse,
    summary="List all executed research experiments",
    tags=["Research - Experiments"],
)
def list_research_experiments(db: Session = Depends(get_db)) -> ResearchExperimentListResponse:
    """Retrieve history of all completed and evaluated research experiment runs."""
    records = db.query(ResearchExperimentModel).order_by(ResearchExperimentModel.created_at.desc()).all()
    results = []
    for r in records:
        cm_dict = json.loads(r.confusion_matrix_json) if r.confusion_matrix_json else {}
        cm_resp = ConfusionMatrixResponse(
            tn=cm_dict.get("tn", 0),
            fp=cm_dict.get("fp", 0),
            fn=cm_dict.get("fn", 0),
            tp=cm_dict.get("tp", 0),
        )
        params = json.loads(r.parameters_json) if r.parameters_json else {}
        runs_sum = json.loads(r.runs_summary_json) if r.runs_summary_json else None
        results.append(
            ResearchExperimentResponse(
                id=r.id,
                dataset_id=r.dataset_id,
                dataset_name=r.dataset_name,
                model_type=r.model_type,
                is_paper_preset=r.is_paper_preset,
                preset_name=r.preset_name,
                parameters=params,
                random_seed=r.random_seed,
                num_runs=r.num_runs,
                status=r.status,
                scaler_init_count=r.scaler_init_count,
                warmup_count=r.warmup_count,
                eval_count=r.eval_count,
                total_evaluation_time_sec=r.total_evaluation_time_sec,
                warmup_time_sec=r.warmup_time_sec,
                avg_latency_per_flow_ms=r.avg_latency_per_flow_ms,
                accuracy=r.accuracy,
                precision=r.precision,
                recall=r.recall,
                f1_score=r.f1_score,
                false_positive_rate=r.false_positive_rate,
                true_positive_rate=r.true_positive_rate,
                confusion_matrix=cm_resp,
                runs_summary=runs_sum,
                error_message=r.error_message,
                created_at=r.created_at,
                completed_at=r.completed_at,
            )
        )
    return ResearchExperimentListResponse(experiments=results, count=len(results))


@app.post(
    "/api/v1/research/experiments/run",
    response_model=ResearchExperimentProgressResponse,
    summary="Start a reproducible research evaluation run",
    tags=["Research - Experiments"],
)
def run_research_experiment(
    req: ResearchExperimentRunRequest,
    db: Session = Depends(get_db),
) -> ResearchExperimentProgressResponse:
    """Launch an asynchronous background experiment evaluating River Online OCSVM or Isolation Forest."""
    dataset = db.query(ResearchDatasetModel).filter(ResearchDatasetModel.id == req.dataset_id).first()
    if not dataset:
        # Fallback to default sample
        dataset = dataset_service.ensure_default_sample_dataset(db)

    params_dict = req.parameters.model_dump() if req.parameters else {}

    try:
        exp_id = experiment_runner.start_experiment(
            dataset_id=dataset.id,
            model_type=req.model_type,
            preset_name=req.preset_name or dataset.version,
            is_paper_preset=req.is_paper_preset,
            parameters=params_dict,
            random_seed=req.random_seed,
            num_runs=req.num_runs,
        )
    except RuntimeError as err:
        raise HTTPException(status_code=409, detail=str(err))

    snapshot = experiment_runner.get_progress_snapshot()
    return ResearchExperimentProgressResponse(**snapshot)


@app.get(
    "/api/v1/research/experiments/active",
    response_model=ResearchExperimentProgressResponse,
    summary="Get live experiment execution progress and status",
    tags=["Research - Experiments"],
)
def get_active_experiment_status() -> ResearchExperimentProgressResponse:
    """Check progress of active or most recently executed experiment."""
    snapshot = experiment_runner.get_progress_snapshot()
    return ResearchExperimentProgressResponse(**snapshot)


@app.post(
    "/api/v1/research/experiments/cancel",
    summary="Cancel the currently running experiment",
    tags=["Research - Experiments"],
)
def cancel_active_experiment():
    """Request immediate graceful cancellation of running background experiment."""
    cancelled = experiment_runner.cancel_active_run()
    if not cancelled:
        return {"status": "ignored", "message": "No active experiment to cancel."}
    return {"status": "cancelled", "message": "Experiment cancellation requested."}


@app.get(
    "/api/v1/research/experiments/{experiment_id}",
    response_model=ResearchExperimentResponse,
    summary="Get single experiment result details",
    tags=["Research - Experiments"],
)
def get_experiment_result(experiment_id: str, db: Session = Depends(get_db)) -> ResearchExperimentResponse:
    """Retrieve full metrics, confusion matrix, and configuration for an experiment run."""
    r = db.query(ResearchExperimentModel).filter(ResearchExperimentModel.id == experiment_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Experiment result not found")

    cm_dict = json.loads(r.confusion_matrix_json) if r.confusion_matrix_json else {}
    cm_resp = ConfusionMatrixResponse(
        tn=cm_dict.get("tn", 0),
        fp=cm_dict.get("fp", 0),
        fn=cm_dict.get("fn", 0),
        tp=cm_dict.get("tp", 0),
    )
    params = json.loads(r.parameters_json) if r.parameters_json else {}
    runs_sum = json.loads(r.runs_summary_json) if r.runs_summary_json else None

    return ResearchExperimentResponse(
        id=r.id,
        dataset_id=r.dataset_id,
        dataset_name=r.dataset_name,
        model_type=r.model_type,
        is_paper_preset=r.is_paper_preset,
        preset_name=r.preset_name,
        parameters=params,
        random_seed=r.random_seed,
        num_runs=r.num_runs,
        status=r.status,
        scaler_init_count=r.scaler_init_count,
        warmup_count=r.warmup_count,
        eval_count=r.eval_count,
        total_evaluation_time_sec=r.total_evaluation_time_sec,
        warmup_time_sec=r.warmup_time_sec,
        avg_latency_per_flow_ms=r.avg_latency_per_flow_ms,
        accuracy=r.accuracy,
        precision=r.precision,
        recall=r.recall,
        f1_score=r.f1_score,
        false_positive_rate=r.false_positive_rate,
        true_positive_rate=r.true_positive_rate,
        confusion_matrix=cm_resp,
        runs_summary=runs_sum,
        error_message=r.error_message,
        created_at=r.created_at,
        completed_at=r.completed_at,
    )


@app.delete(
    "/api/v1/research/experiments/{experiment_id}",
    summary="Delete an experiment run record",
    tags=["Research - Experiments"],
)
def delete_experiment_record(experiment_id: str, db: Session = Depends(get_db)):
    """Delete an experiment record from database history."""
    r = db.query(ResearchExperimentModel).filter(ResearchExperimentModel.id == experiment_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Experiment record not found")
    db.delete(r)
    db.commit()
    return {"status": "ok", "message": f"Experiment '{experiment_id}' deleted."}


@app.get(
    "/api/v1/research/reference",
    response_model=List[PaperReferenceMetricResponse],
    summary="Get published benchmark results from Miguel-Diez et al. (arXiv:2509.01375)",
    tags=["Research - Documentation"],
)
def get_paper_reference_benchmarks() -> List[PaperReferenceMetricResponse]:
    """Retrieve theoretical reference benchmarks published in the selected research paper."""
    return [PaperReferenceMetricResponse(**ref) for ref in PUBLISHED_PAPER_RESULTS]


@app.get(
    "/api/v1/research/compare",
    response_model=ComparisonSummaryResponse,
    summary="Compare proposed online model, baseline, and paper benchmarks",
    tags=["Research - Evaluation"],
)
def get_comparison_summary(db: Session = Depends(get_db)) -> ComparisonSummaryResponse:
    """Retrieve side-by-side comparison between latest River Online OCSVM and Baseline Isolation Forest."""
    proposed_rec = (
        db.query(ResearchExperimentModel)
        .filter(ResearchExperimentModel.model_type == "river_ocsvm", ResearchExperimentModel.status == "completed")
        .order_by(ResearchExperimentModel.created_at.desc())
        .first()
    )
    baseline_rec = (
        db.query(ResearchExperimentModel)
        .filter(ResearchExperimentModel.model_type == "isolation_forest", ResearchExperimentModel.status == "completed")
        .order_by(ResearchExperimentModel.created_at.desc())
        .first()
    )

    def to_schema(r: Optional[ResearchExperimentModel]) -> Optional[ResearchExperimentResponse]:
        if not r:
            return None
        cm = json.loads(r.confusion_matrix_json) if r.confusion_matrix_json else {}
        return ResearchExperimentResponse(
            id=r.id,
            dataset_id=r.dataset_id,
            dataset_name=r.dataset_name,
            model_type=r.model_type,
            is_paper_preset=r.is_paper_preset,
            preset_name=r.preset_name,
            parameters=json.loads(r.parameters_json) if r.parameters_json else {},
            random_seed=r.random_seed,
            num_runs=r.num_runs,
            status=r.status,
            scaler_init_count=r.scaler_init_count,
            warmup_count=r.warmup_count,
            eval_count=r.eval_count,
            total_evaluation_time_sec=r.total_evaluation_time_sec,
            warmup_time_sec=r.warmup_time_sec,
            avg_latency_per_flow_ms=r.avg_latency_per_flow_ms,
            accuracy=r.accuracy,
            precision=r.precision,
            recall=r.recall,
            f1_score=r.f1_score,
            false_positive_rate=r.false_positive_rate,
            true_positive_rate=r.true_positive_rate,
            confusion_matrix=ConfusionMatrixResponse(**cm),
            runs_summary=json.loads(r.runs_summary_json) if r.runs_summary_json else None,
            error_message=r.error_message,
            created_at=r.created_at,
            completed_at=r.completed_at,
        )

    ref_list = [PaperReferenceMetricResponse(**ref) for ref in PUBLISHED_PAPER_RESULTS]

    return ComparisonSummaryResponse(
        proposed_model=to_schema(proposed_rec),
        baseline_model=to_schema(baseline_rec),
        paper_reference=ref_list,
    )
