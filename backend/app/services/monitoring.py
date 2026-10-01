"""Background monitoring service coordinating live metric collection, SQLite persistence, and WebSocket broadcasting."""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import List, Optional, Set
from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.collector import (
    CountersUnavailableError,
    InterfaceNotFoundError,
    NetworkCollectorError,
    NetworkMetrics,
    NetworkTrafficCollector,
)
from app.database import SessionLocal
from app.models import AnomalyEventModel, NetworkMetricModel
from app.schemas import (
    AnomalyEvaluationSchema,
    AnomalyEventResponse,
    AnomalySummaryResponse,
    InterfaceDetail,
    MonitoringSummaryResponse,
    NetworkMetricResponse,
)
from app.services.anomaly import AnomalyDetector, AnomalyEvaluationResult

logger = logging.getLogger("network_monitoring.service")


class MonitoringService:
    """Manages the background telemetry collection loop, SQLite database persistence, and WebSocket client subscriptions."""

    def __init__(
        self,
        collector: Optional[NetworkTrafficCollector] = None,
        session_factory: Optional[object] = None,
        default_interval: float = 1.0,
    ) -> None:
        self.collector = collector or NetworkTrafficCollector()
        self.session_factory = session_factory or SessionLocal
        self.interval_seconds = default_interval
        self.active_interface: Optional[str] = None

        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

        # Telemetry tracking
        self._latest_metrics: Optional[NetworkMetrics] = None
        self._latest_persisted_id: Optional[int] = None
        self._start_time: Optional[datetime] = None
        self._start_monotonic: Optional[float] = None
        self._peak_upload_mbps: float = 0.0
        self._peak_download_mbps: float = 0.0
        self._session_sample_count: int = 0

        # AI Anomaly Detection Engine
        self.anomaly_detector = AnomalyDetector()
        self._latest_anomaly_result: Optional[AnomalyEvaluationResult] = None
        self._last_persisted_anomaly_time: Optional[float] = None
        self._last_persisted_anomaly_severity: Optional[str] = None
        self._training_task: Optional[asyncio.Task] = None

        # WebSocket subscriptions
        self._subscribers: Set[WebSocket] = set()

    def get_available_interfaces(self) -> List[str]:
        """Query host for available network interface names."""
        return self.collector.get_available_interfaces()

    def get_interface_details(self) -> List[InterfaceDetail]:
        """Fetch detailed status for all available interfaces."""
        details: List[InterfaceDetail] = []
        for name in self.get_available_interfaces():
            try:
                sample = self.collector.get_raw_sample(name)
                details.append(
                    InterfaceDetail(
                        name=name,
                        bytes_sent=sample.bytes_sent,
                        bytes_recv=sample.bytes_recv,
                        packets_sent=sample.packets_sent,
                        packets_recv=sample.packets_recv,
                        is_up=True,
                        speed_mbps=None,
                    )
                )
            except Exception as exc:
                logger.debug("Failed reading interface %s: %s", name, exc)
        return details

    def select_default_interface(self) -> Optional[str]:
        """Intelligently select the best active network interface.

        Prefers interfaces with highest cumulative byte counters (e.g. active Wi-Fi or Ethernet)
        excluding inactive/loopback adapters when possible.
        """
        interfaces = self.get_available_interfaces()
        if not interfaces:
            return None

        # Prefer non-loopback with largest cumulative traffic
        best_iface = None
        max_bytes = -1

        for name in interfaces:
            try:
                sample = self.collector.get_raw_sample(name)
                total_bytes = sample.bytes_sent + sample.bytes_recv
                # Prioritize Wi-Fi or Ethernet adapters
                priority_bonus = (
                    1_000_000_000
                    if any(k in name.lower() for k in ("wi-fi", "ethernet", "wlan", "eth"))
                    else 0
                )
                score = total_bytes + priority_bonus
                if score > max_bytes:
                    max_bytes = score
                    best_iface = name
            except Exception:
                continue

        return best_iface or interfaces[0]

    async def start(
        self,
        interface: Optional[str] = None,
        interval: Optional[float] = None,
    ) -> None:
        """Start or reconfigure the background monitoring loop safely."""
        async with self._lock:
            if interval and interval > 0:
                self.interval_seconds = interval

            target_interface = interface or self.active_interface or self.select_default_interface()
            if not target_interface:
                logger.warning("No network interface available to monitor.")
                return

            # If already running on the same interface, nothing to do
            if self._is_running and self._task and not self._task.done() and self.active_interface == target_interface:
                return

            # If switching interfaces or starting fresh
            if self._is_running:
                await self._stop_internal()

            self.active_interface = target_interface
            self.collector.reset(self.active_interface)
            self.anomaly_detector.reset(self.active_interface)
            self._latest_anomaly_result = None
            self._last_persisted_anomaly_time = None
            self._last_persisted_anomaly_severity = None
            self._is_running = True
            self._start_monotonic = asyncio.get_running_loop().time()
            self._start_time = datetime.now(timezone.utc)
            self._peak_upload_mbps = 0.0
            self._peak_download_mbps = 0.0
            self._session_sample_count = 0

            self._task = asyncio.create_task(
                self._monitoring_loop(),
                name=f"monitoring-loop-{self.active_interface}",
            )
            logger.info("Started network monitoring on interface '%s'", self.active_interface)

    async def stop(self) -> None:
        """Gracefully stop the background monitoring loop."""
        async with self._lock:
            await self._stop_internal()

    async def _stop_internal(self) -> None:
        """Internal helper to cancel and await background task without re-acquiring lock."""
        self._is_running = False
        if self._training_task and not self._training_task.done():
            self._training_task.cancel()
            self._training_task = None
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Stopped network monitoring")

    async def _monitoring_loop(self) -> None:
        """Main asynchronous collection and persistence loop."""
        while self._is_running:
            if not self.active_interface:
                await asyncio.sleep(self.interval_seconds)
                continue

            try:
                metrics = self.collector.collect(self.active_interface)
                self._latest_metrics = metrics

                if not metrics.is_initial_sample:
                    self._session_sample_count += 1
                    self._peak_upload_mbps = max(self._peak_upload_mbps, metrics.upload_mbps)
                    self._peak_download_mbps = max(self._peak_download_mbps, metrics.download_mbps)

                    # 1. AI Anomaly Engine Evaluation
                    anomaly_result = self.anomaly_detector.evaluate(metrics)
                    self._latest_anomaly_result = anomaly_result

                    # Non-blocking model training trigger in worker thread
                    if (
                        self.anomaly_detector.is_warmed_up
                        and (
                            not self.anomaly_detector.is_trained
                            or (self.anomaly_detector._samples_observed - self.anomaly_detector._last_trained_sample_count >= 100)
                        )
                    ):
                        if self._training_task is None or self._training_task.done():
                            self._training_task = asyncio.create_task(
                                asyncio.to_thread(self.anomaly_detector.train),
                                name="anomaly-detector-train",
                            )

                    # 2. Persist metric sample to SQLite
                    persisted_id = await self._persist_metric(metrics)
                    self._latest_persisted_id = persisted_id

                    # 3. Anomaly event persistence & alert policy
                    if anomaly_result.is_anomaly:
                        loop_time = asyncio.get_running_loop().time()
                        time_since_last = (
                            loop_time - self._last_persisted_anomaly_time
                            if self._last_persisted_anomaly_time is not None
                            else 999999.0
                        )
                        is_escalation = (
                            self._last_persisted_anomaly_severity == AnomalyDetector.SEVERITY_UNUSUAL
                            and anomaly_result.severity == AnomalyDetector.SEVERITY_HIGH
                        )
                        # Persist at most once per 10s for ongoing anomaly, unless severity escalates
                        if time_since_last >= 10.0 or is_escalation:
                            anomaly_event_id = await self._persist_anomaly_event(anomaly_result)
                            self._last_persisted_anomaly_time = loop_time
                            self._last_persisted_anomaly_severity = anomaly_result.severity
                            await self._broadcast_anomaly_event(anomaly_result, anomaly_event_id)

                    # 4. Broadcast live metric (with enriched anomaly data) to WebSockets
                    await self._broadcast_metric(metrics, persisted_id, anomaly_result)

            except (InterfaceNotFoundError, CountersUnavailableError) as exc:
                logger.warning("Monitoring warning for interface '%s': %s", self.active_interface, exc)
            except Exception as exc:
                logger.exception("Unexpected error in monitoring loop: %s", exc)

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

    async def _persist_metric(self, metrics: NetworkMetrics) -> Optional[int]:
        """Save a single sample into SQLite via SQLAlchemy session."""
        def _db_insert():
            db: Session = self.session_factory()
            try:
                record = NetworkMetricModel(
                    timestamp=datetime.fromtimestamp(metrics.timestamp, tz=timezone.utc),
                    interface=metrics.interface_name,
                    upload_mbps=metrics.upload_mbps,
                    download_mbps=metrics.download_mbps,
                    packets_sent_per_sec=metrics.packets_sent_per_sec,
                    packets_received_per_sec=metrics.packets_recv_per_sec,
                    cumulative_sent_mb=round(metrics.cumulative_bytes_sent / (1024 * 1024), 2),
                    cumulative_received_mb=round(metrics.cumulative_bytes_recv / (1024 * 1024), 2),
                    session_transferred_mb=metrics.session_transferred_mb,
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                return record.id
            except Exception as exc:
                db.rollback()
                logger.error("Failed to persist network metric to database: %s", exc)
                return None
            finally:
                db.close()

        return await asyncio.to_thread(_db_insert)

    async def _persist_anomaly_event(self, result: AnomalyEvaluationResult) -> Optional[int]:
        """Save detected anomaly event to SQLite via thread pool."""
        def _db_insert():
            db: Session = self.session_factory()
            try:
                record = AnomalyEventModel(
                    timestamp=result.timestamp,
                    interface=result.interface,
                    anomaly_score=result.anomaly_score,
                    severity=result.severity,
                    detection_method=result.detection_method,
                    metrics_snapshot=json.dumps(result.metrics_snapshot),
                    explanation=result.explanation,
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                return record.id
            except Exception as exc:
                db.rollback()
                logger.error("Failed to persist anomaly event to database: %s", exc)
                return None
            finally:
                db.close()

        return await asyncio.to_thread(_db_insert)

    async def _broadcast_anomaly_event(
        self, result: AnomalyEvaluationResult, event_id: Optional[int]
    ) -> None:
        """Broadcast real-time anomaly alert event to connected WebSocket subscribers."""
        if not self._subscribers:
            return

        payload = {
            "type": "anomaly_event",
            "data": {
                "id": event_id,
                "timestamp": result.timestamp.isoformat(),
                "interface": result.interface,
                "anomaly_score": result.anomaly_score,
                "severity": result.severity,
                "detection_method": result.detection_method,
                "explanation": result.explanation,
                "metrics_snapshot": result.metrics_snapshot,
            },
        }
        message_text = json.dumps(payload)
        disconnected = []
        for ws in list(self._subscribers):
            try:
                await ws.send_text(message_text)
            except Exception:
                disconnected.append(ws)
        for dead_ws in disconnected:
            self._subscribers.discard(dead_ws)

    async def _broadcast_metric(
        self,
        metrics: NetworkMetrics,
        record_id: Optional[int],
        anomaly_result: Optional[AnomalyEvaluationResult] = None,
    ) -> None:
        """Broadcast live metric to all active WebSocket subscribers."""
        if not self._subscribers:
            return

        payload = {
            "type": "metric_update",
            "data": {
                "id": record_id,
                "timestamp": datetime.fromtimestamp(metrics.timestamp, tz=timezone.utc).isoformat(),
                "interface": metrics.interface_name,
                "upload_mbps": metrics.upload_mbps,
                "download_mbps": metrics.download_mbps,
                "packets_sent_per_sec": metrics.packets_sent_per_sec,
                "packets_received_per_sec": metrics.packets_recv_per_sec,
                "cumulative_sent_mb": round(metrics.cumulative_bytes_sent / (1024 * 1024), 2),
                "cumulative_received_mb": round(metrics.cumulative_bytes_recv / (1024 * 1024), 2),
                "session_transferred_mb": metrics.session_transferred_mb,
                "is_initial_sample": metrics.is_initial_sample,
            },
        }
        if anomaly_result:
            payload["data"]["anomaly"] = {
                "score": anomaly_result.anomaly_score,
                "severity": anomaly_result.severity,
                "is_anomaly": anomaly_result.is_anomaly,
                "method": anomaly_result.detection_method,
                "explanation": anomaly_result.explanation,
            }

        message_text = json.dumps(payload)

        disconnected: List[WebSocket] = []
        for ws in list(self._subscribers):
            try:
                await ws.send_text(message_text)
            except Exception:
                disconnected.append(ws)

        for dead_ws in disconnected:
            self._subscribers.discard(dead_ws)

    async def broadcast_event(self, payload: dict) -> None:
        """Broadcast arbitrary JSON event payload to all active WebSocket subscribers."""
        if not self._subscribers:
            return
        message_text = json.dumps(payload)
        disconnected: List[WebSocket] = []
        for ws in list(self._subscribers):
            try:
                await ws.send_text(message_text)
            except Exception:
                disconnected.append(ws)

        for dead_ws in disconnected:
            self._subscribers.discard(dead_ws)

    async def connect_websocket(self, websocket: WebSocket) -> None:
        """Register a new WebSocket connection and send current snapshot if available."""
        await websocket.accept()
        self._subscribers.add(websocket)
        logger.info("WebSocket connected (%d total)", len(self._subscribers))

        # Send latest metric snapshot immediately if available
        if self._latest_metrics:
            try:
                snapshot = {
                    "type": "initial_state",
                    "data": {
                        "id": self._latest_persisted_id,
                        "timestamp": datetime.fromtimestamp(
                            self._latest_metrics.timestamp, tz=timezone.utc
                        ).isoformat(),
                        "interface": self._latest_metrics.interface_name,
                        "upload_mbps": self._latest_metrics.upload_mbps,
                        "download_mbps": self._latest_metrics.download_mbps,
                        "packets_sent_per_sec": self._latest_metrics.packets_sent_per_sec,
                        "packets_received_per_sec": self._latest_metrics.packets_recv_per_sec,
                        "cumulative_sent_mb": round(
                            self._latest_metrics.cumulative_bytes_sent / (1024 * 1024), 2
                        ),
                        "cumulative_received_mb": round(
                            self._latest_metrics.cumulative_bytes_recv / (1024 * 1024), 2
                        ),
                        "session_transferred_mb": self._latest_metrics.session_transferred_mb,
                        "is_initial_sample": self._latest_metrics.is_initial_sample,
                    },
                }
                await websocket.send_text(json.dumps(snapshot))
            except Exception:
                pass

    def disconnect_websocket(self, websocket: WebSocket) -> None:
        """Unregister a disconnected WebSocket client."""
        self._subscribers.discard(websocket)
        logger.info("WebSocket disconnected (%d remaining)", len(self._subscribers))

    def get_current_metric_response(self) -> Optional[NetworkMetricResponse]:
        """Return the most recent collected metric formatted as schema."""
        if not self._latest_metrics:
            return None

        m = self._latest_metrics
        anomaly_schema = None
        if self._latest_anomaly_result:
            r = self._latest_anomaly_result
            anomaly_schema = AnomalyEvaluationSchema(
                score=r.anomaly_score,
                severity=r.severity,
                is_anomaly=r.is_anomaly,
                method=r.detection_method,
                explanation=r.explanation,
            )

        return NetworkMetricResponse(
            id=self._latest_persisted_id,
            timestamp=datetime.fromtimestamp(m.timestamp, tz=timezone.utc),
            interface=m.interface_name,
            upload_mbps=m.upload_mbps,
            download_mbps=m.download_mbps,
            packets_sent_per_sec=m.packets_sent_per_sec,
            packets_received_per_sec=m.packets_recv_per_sec,
            cumulative_sent_mb=round(m.cumulative_bytes_sent / (1024 * 1024), 2),
            cumulative_received_mb=round(m.cumulative_bytes_recv / (1024 * 1024), 2),
            session_transferred_mb=m.session_transferred_mb,
            is_initial_sample=m.is_initial_sample,
            anomaly=anomaly_schema,
        )

    def get_summary(self, db: Session) -> MonitoringSummaryResponse:
        """Produce aggregated summary statistics for the active monitoring session."""
        total_db_samples = db.query(NetworkMetricModel).count()

        cur_up = self._latest_metrics.upload_mbps if self._latest_metrics else 0.0
        cur_down = self._latest_metrics.download_mbps if self._latest_metrics else 0.0
        session_mb = self._latest_metrics.session_transferred_mb if self._latest_metrics else 0.0
        cum_sent = (
            round(self._latest_metrics.cumulative_bytes_sent / (1024 * 1024), 2)
            if self._latest_metrics
            else 0.0
        )
        cum_recv = (
            round(self._latest_metrics.cumulative_bytes_recv / (1024 * 1024), 2)
            if self._latest_metrics
            else 0.0
        )

        duration = 0.0
        if self._start_time:
            duration = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        return MonitoringSummaryResponse(
            interface=self.active_interface,
            is_monitoring=self._is_running,
            current_upload_mbps=cur_up,
            current_download_mbps=cur_down,
            peak_upload_mbps=round(self._peak_upload_mbps, 4),
            peak_download_mbps=round(self._peak_download_mbps, 4),
            session_transferred_mb=round(session_mb, 3),
            cumulative_sent_mb=cum_sent,
            cumulative_received_mb=cum_recv,
            total_stored_samples=total_db_samples,
            session_samples_collected=self._session_sample_count,
            monitoring_duration_seconds=round(max(0.0, duration), 1),
        )

    def get_anomaly_summary(self, db: Session) -> AnomalySummaryResponse:
        """Query SQLite for cumulative anomaly counts and return engine status."""
        total_count = db.query(AnomalyEventModel).count()
        unusual_count = (
            db.query(AnomalyEventModel)
            .filter(AnomalyEventModel.severity == AnomalyDetector.SEVERITY_UNUSUAL)
            .count()
        )
        high_count = (
            db.query(AnomalyEventModel)
            .filter(AnomalyEventModel.severity == AnomalyDetector.SEVERITY_HIGH)
            .count()
        )

        latest_record = (
            db.query(AnomalyEventModel)
            .order_by(AnomalyEventModel.timestamp.desc())
            .first()
        )
        latest_resp = None
        if latest_record:
            latest_resp = AnomalyEventResponse(
                id=latest_record.id,
                timestamp=latest_record.timestamp,
                interface=latest_record.interface,
                anomaly_score=latest_record.anomaly_score,
                severity=latest_record.severity,
                detection_method=latest_record.detection_method,
                metrics_snapshot=latest_record.metrics_snapshot,
                explanation=latest_record.explanation,
            )

        return AnomalySummaryResponse(
            total_anomalies=total_count,
            unusual_traffic_count=unusual_count,
            high_anomaly_count=high_count,
            latest_anomaly=latest_resp,
            model_status=self.anomaly_detector.status,
            is_trained=self.anomaly_detector.is_trained,
            samples_observed=self.anomaly_detector._samples_observed,
            active_interface=self.active_interface,
        )



# Global singleton monitoring service instance
monitoring_service = MonitoringService()
