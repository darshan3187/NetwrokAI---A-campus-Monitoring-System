"""Asynchronous Device Polling Service (Phase 2).

Orchestrates periodic telemetry collection for registered campus devices
whose polling has been explicitly enabled. Applies concurrency locking,
failure isolation, rate computation, SQLite persistence, and WebSocket broadcasting.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict, Optional, Set
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import DeviceModel, DeviceTelemetryModel
from app.services.remote_collector import (
    BaseRemoteCollector,
    ComputedInterfaceMetrics,
    DevicePollResult,
    RateCalculator,
    collector_factory,
)

logger = logging.getLogger("network_monitoring.polling")


class DevicePollingService:
    """Manages background polling jobs for registered campus devices."""

    def __init__(
        self,
        session_factory=None,
        default_poll_timeout: float = 3.0,
        rate_calculator: Optional[RateCalculator] = None,
    ) -> None:
        self.session_factory = session_factory or SessionLocal
        self.default_poll_timeout = default_poll_timeout
        self.rate_calculator = rate_calculator or RateCalculator()

        self._is_running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._active_polls: Set[str] = set()  # Tracks device IDs currently being polled to prevent overlap
        self._lock = asyncio.Lock()

        # Telemetry broadcast callback (wired to monitoring_service)
        self.broadcast_callback = None

    async def start(self) -> None:
        """Start the background device polling scheduler loop."""
        async with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())
            logger.info("Campus Device Polling Engine started.")

    async def stop(self) -> None:
        """Gracefully stop all polling tasks and wait for scheduler loop termination."""
        async with self._lock:
            if not self._is_running:
                return
            self._is_running = False
            if self._scheduler_task:
                self._scheduler_task.cancel()
                try:
                    await self._scheduler_task
                except asyncio.CancelledError:
                    pass
                self._scheduler_task = None
            logger.info("Campus Device Polling Engine stopped.")

    async def _scheduler_loop(self) -> None:
        """Periodically inspects enabled devices and schedules non-overlapping poll jobs."""
        logger.info("Device polling scheduler loop initialized.")
        while self._is_running:
            try:
                db: Session = self.session_factory()
                try:
                    # Query devices explicitly enabled and active
                    devices = (
                        db.query(DeviceModel)
                        .filter(
                            DeviceModel.polling_enabled == True,
                            DeviceModel.monitoring_status == "active",
                        )
                        .all()
                    )

                    now = datetime.now(timezone.utc)
                    for dev in devices:
                        # Check cadence
                        interval = dev.polling_interval_seconds or 10.0
                        last_poll = dev.last_poll_at
                        should_poll = False

                        if last_poll is None:
                            should_poll = True
                        else:
                            # Ensure last_poll has timezone info for comparison
                            if last_poll.tzinfo is None:
                                last_poll = last_poll.replace(tzinfo=timezone.utc)
                            elapsed = (now - last_poll).total_seconds()
                            if elapsed >= interval:
                                should_poll = True

                        if should_poll and dev.id not in self._active_polls:
                            # Spawn isolated async task per device
                            asyncio.create_task(self.poll_device_job(dev.id))

                finally:
                    db.close()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Error in device polling scheduler tick: %s", exc)

            # Sleep 1 second between scheduler checks
            try:
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break

    async def poll_device_job(self, device_id: str) -> Optional[DevicePollResult]:
        """Execute a single polling cycle against a specific device with concurrency protection."""
        if device_id in self._active_polls:
            logger.debug("Skipping poll for device '%s'; job already in progress.", device_id)
            return None

        self._active_polls.add(device_id)
        try:
            return await self._execute_poll(device_id)
        finally:
            self._active_polls.discard(device_id)

    async def _execute_poll(self, device_id: str) -> Optional[DevicePollResult]:
        """Poll telemetry from device, update operational state, compute rates, and persist."""
        db: Session = self.session_factory()
        try:
            device = db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
            if not device:
                logger.warning("Device '%s' not found during poll execution.", device_id)
                return None

            collector = collector_factory.get_collector(device.collection_method)
            timeout = self.default_poll_timeout

            # Poll device
            poll_result = await collector.poll(
                target_ip=device.ip_address,
                device_id=device.id,
                timeout_seconds=timeout,
            )

            now_dt = datetime.now(timezone.utc)
            device.last_poll_at = now_dt
            device.reachability = poll_result.reachability
            device.last_poll_error = poll_result.error_message

            if poll_result.success:
                device.last_poll_status = "success"
                device.connection_status = "online"

                # Compute and persist interface metrics
                is_mock = (device.collection_method in ("mock", "manual"))
                for raw_iface in poll_result.interfaces:
                    computed = self.rate_calculator.calculate_metrics(
                        device_id=device.id,
                        current=raw_iface,
                        is_mock=is_mock,
                    )

                    metric_record = DeviceTelemetryModel(
                        device_id=device.id,
                        interface_index=computed.interface_index,
                        interface_name=computed.interface_name,
                        timestamp=datetime.fromtimestamp(computed.timestamp, tz=timezone.utc),
                        bytes_sent=computed.bytes_sent,
                        bytes_recv=computed.bytes_recv,
                        packets_sent=computed.packets_sent,
                        packets_recv=computed.packets_recv,
                        upload_mbps=computed.upload_mbps,
                        download_mbps=computed.download_mbps,
                        packets_sent_per_sec=computed.packets_sent_per_sec,
                        packets_recv_per_sec=computed.packets_recv_per_sec,
                        errors_in=computed.errors_in,
                        errors_out=computed.errors_out,
                        discards_in=computed.discards_in,
                        discards_out=computed.discards_out,
                        collection_method=device.collection_method,
                        data_validity=computed.data_validity,
                        oper_status=computed.oper_status,
                    )
                    db.add(metric_record)

                    # Broadcast over WebSocket if callback configured
                    if self.broadcast_callback:
                        try:
                            payload = {
                                "type": "device_telemetry",
                                "device_id": device.id,
                                "data": {
                                    "device_id": device.id,
                                    "interface_name": computed.interface_name,
                                    "timestamp": datetime.fromtimestamp(
                                        computed.timestamp, tz=timezone.utc
                                    ).isoformat(),
                                    "upload_mbps": computed.upload_mbps,
                                    "download_mbps": computed.download_mbps,
                                    "packets_sent_per_sec": computed.packets_sent_per_sec,
                                    "packets_recv_per_sec": computed.packets_recv_per_sec,
                                    "oper_status": computed.oper_status,
                                    "data_validity": computed.data_validity,
                                    "collection_method": device.collection_method,
                                },
                            }
                            asyncio.create_task(self.broadcast_callback(payload))
                        except Exception as b_exc:
                            logger.debug("Failed broadcasting device telemetry: %s", b_exc)

            else:
                device.last_poll_status = "error"
                if poll_result.reachability == "unreachable":
                    device.connection_status = "offline"

            db.commit()
            return poll_result

        except Exception as exc:
            logger.error("Exception during poll execution for device '%s': %s", device_id, exc)
            try:
                db.rollback()
                device = db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
                if device:
                    device.last_poll_status = "error"
                    device.last_poll_error = f"Internal polling exception: {exc}"
                    device.reachability = "unreachable"
                    device.connection_status = "offline"
                    db.commit()
            except Exception:
                pass
            return None
        finally:
            db.close()

    def enable_polling(self, db: Session, device_id: str, interval_seconds: Optional[float] = None) -> Optional[DeviceModel]:
        """Enable active background polling on a registered device."""
        device = db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
        if not device:
            return None

        device.polling_enabled = True
        if interval_seconds is not None:
            device.polling_interval_seconds = max(1.0, interval_seconds)

        db.commit()
        db.refresh(device)
        logger.info("Enabled polling for device '%s' (interval=%.1fs)", device.id, device.polling_interval_seconds)
        return device

    def disable_polling(self, db: Session, device_id: str) -> Optional[DeviceModel]:
        """Disable active background polling on a registered device."""
        device = db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
        if not device:
            return None

        device.polling_enabled = False
        db.commit()
        db.refresh(device)
        logger.info("Disabled polling for device '%s'", device.id)
        return device


polling_service = DevicePollingService()
