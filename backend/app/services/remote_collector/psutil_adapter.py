import asyncio
import time
from typing import List
import psutil
from app.collector import NetworkTrafficCollector
from app.services.remote_collector.base import (
    BaseRemoteCollector,
    DevicePollResult,
    RawInterfaceCounters,
)


class LocalPsutilAdapter(BaseRemoteCollector):
    """Adapts host-level psutil telemetry collector to the remote collector interface."""

    def __init__(self, collector: NetworkTrafficCollector = None) -> None:
        self.collector = collector or NetworkTrafficCollector()

    async def poll(
        self,
        target_ip: str,
        device_id: str,
        timeout_seconds: float = 3.0,
    ) -> DevicePollResult:
        """Poll host interfaces via psutil."""
        now = time.time()
        interfaces: List[RawInterfaceCounters] = []

        try:
            avail = self.collector.get_available_interfaces()
            for idx, name in enumerate(avail, start=1):
                try:
                    raw = self.collector.get_raw_sample(name)
                    interfaces.append(
                        RawInterfaceCounters(
                            index=idx,
                            name=name,
                            oper_status="up",
                            bytes_sent=raw.bytes_sent,
                            bytes_recv=raw.bytes_recv,
                            packets_sent=raw.packets_sent,
                            packets_recv=raw.packets_recv,
                            errors_in=raw.errin,
                            errors_out=raw.errout,
                            discards_in=raw.dropin,
                            discards_out=raw.dropout,
                            timestamp=now,
                        )
                    )
                except Exception:
                    pass

            return DevicePollResult(
                device_id=device_id,
                success=True,
                reachability="reachable",
                latency_ms=0.5,
                error_message=None,
                interfaces=interfaces,
                system_uptime=time.time() - psutil.boot_time() if hasattr(psutil, "boot_time") else None,
                system_descr="Local Host Operating System (psutil adapter)",
                timestamp=now,
            )
        except Exception as exc:
            return DevicePollResult(
                device_id=device_id,
                success=False,
                reachability="unreachable",
                error_message=f"Local host collector error: {exc}",
                timestamp=now,
            )
