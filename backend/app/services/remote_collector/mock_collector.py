"""Mock collector for deterministic development, testing, and isolated simulation (Phase 2)."""

import asyncio
import time
from typing import Dict, List, Optional
from app.services.remote_collector.base import (
    BaseRemoteCollector,
    DevicePollResult,
    RawInterfaceCounters,
)


class MockRemoteCollector(BaseRemoteCollector):
    """Generates synthetic, deterministic interface counter telemetry for development and testing.

    Always marks data validity as 'mock' to guarantee that synthetic data is never
    misrepresented as live college network traffic.
    """

    def __init__(
        self,
        default_latency_ms: float = 12.0,
        bytes_increment_per_sec: int = 150_000,
        packets_increment_per_sec: int = 250,
    ) -> None:
        self.default_latency_ms = default_latency_ms
        self.bytes_increment_per_sec = bytes_increment_per_sec
        self.packets_increment_per_sec = packets_increment_per_sec

        # State storage per device_id: dict of interface_name -> counter dict
        self._device_state: Dict[str, Dict[str, dict]] = {}
        # Fault injection controls for automated testing
        self.forced_reachability: Optional[str] = None
        self.simulate_timeout: bool = False
        self.simulate_unsupported: bool = False
        self.trigger_counter_reset: bool = False

    def inject_fault(self, device_id: Optional[str] = None, fault_type: str = "unreachable") -> None:
        """Inject reachability or failure condition for testing ('unreachable', 'unsupported', 'timeout', 'reset')."""
        if fault_type == "timeout":
            self.simulate_timeout = True
        elif fault_type == "reset":
            self.trigger_counter_reset = True
        elif fault_type in ("unreachable", "unsupported"):
            self.forced_reachability = fault_type

    def clear_faults(self) -> None:
        """Reset fault injection state back to normal operational behavior."""
        self.forced_reachability = None
        self.simulate_timeout = False
        self.simulate_unsupported = False
        self.trigger_counter_reset = False

    async def poll(
        self,
        target_ip: str,
        device_id: str,
        timeout_seconds: float = 3.0,
    ) -> DevicePollResult:
        """Simulate polling a remote router, switch, or access point."""
        now = time.time()

        if self.simulate_timeout:
            await asyncio.sleep(min(0.05, timeout_seconds))
            return DevicePollResult(
                device_id=device_id,
                success=False,
                reachability="unreachable",
                latency_ms=timeout_seconds * 1000.0,
                error_message="Connection timed out waiting for response from target.",
                timestamp=now,
            )

        if self.forced_reachability == "unreachable":
            await asyncio.sleep(0.01)
            return DevicePollResult(
                device_id=device_id,
                success=False,
                reachability="unreachable",
                latency_ms=self.default_latency_ms,
                error_message="Host unreachable (ICMP Destination Unreachable / No route to host).",
                timestamp=now,
            )

        if self.simulate_unsupported or self.forced_reachability == "unsupported":
            await asyncio.sleep(0.01)
            return DevicePollResult(
                device_id=device_id,
                success=False,
                reachability="unsupported",
                latency_ms=self.default_latency_ms,
                error_message="Target device does not support standard MIB-II interface counters (OID unsupported).",
                timestamp=now,
            )

        # Normal successful poll simulation
        await asyncio.sleep(0.01)

        if device_id not in self._device_state:
            # Initialize baseline counters
            self._device_state[device_id] = {
                "GigabitEthernet0/1": {
                    "index": 1,
                    "bytes_recv": 50_000_000,
                    "bytes_sent": 25_000_000,
                    "pkts_recv": 350_000,
                    "pkts_sent": 180_000,
                    "last_poll": now,
                },
                "GigabitEthernet0/2": {
                    "index": 2,
                    "bytes_recv": 12_000_000,
                    "bytes_sent": 8_000_000,
                    "pkts_recv": 90_000,
                    "pkts_sent": 60_000,
                    "last_poll": now,
                },
            }

        dev_data = self._device_state[device_id]
        interfaces: List[RawInterfaceCounters] = []

        for iface_name, state in dev_data.items():
            last_t = state["last_poll"]
            elapsed = max(0.1, now - last_t)
            state["last_poll"] = now

            if self.trigger_counter_reset:
                # Simulate device reboot / counter rollover
                state["bytes_recv"] = 5_000
                state["bytes_sent"] = 2_000
                state["pkts_recv"] = 40
                state["pkts_sent"] = 20
            else:
                # Monotonic progression
                rx_inc = int(self.bytes_increment_per_sec * elapsed)
                tx_inc = int((self.bytes_increment_per_sec * 0.6) * elapsed)
                rx_p_inc = int(self.packets_increment_per_sec * elapsed)
                tx_p_inc = int((self.packets_increment_per_sec * 0.5) * elapsed)

                state["bytes_recv"] += rx_inc
                state["bytes_sent"] += tx_inc
                state["pkts_recv"] += rx_p_inc
                state["pkts_sent"] += tx_p_inc

            interfaces.append(
                RawInterfaceCounters(
                    index=state["index"],
                    name=iface_name,
                    oper_status="up",
                    bytes_sent=state["bytes_sent"],
                    bytes_recv=state["bytes_recv"],
                    packets_sent=state["pkts_sent"],
                    packets_recv=state["pkts_recv"],
                    errors_in=0,
                    errors_out=0,
                    discards_in=0,
                    discards_out=0,
                    speed_bps=1_000_000_000,
                    timestamp=now,
                )
            )

        return DevicePollResult(
            device_id=device_id,
            success=True,
            reachability="reachable",
            latency_ms=self.default_latency_ms,
            error_message=None,
            interfaces=interfaces,
            system_uptime=3600.0,
            system_descr="NetworkAI Mock Campus Router (Simulated Hardware)",
            timestamp=now,
        )
