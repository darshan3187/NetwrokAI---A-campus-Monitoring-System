"""Base abstractions and data contracts for remote network device collectors (Phase 2)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time
from typing import List, Optional


@dataclass(frozen=True)
class RawInterfaceCounters:
    """Raw snapshot of interface statistics read from a remote device."""

    index: Optional[int]
    name: str
    oper_status: str  # up, down, testing, unknown
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errors_in: int = 0
    errors_out: int = 0
    discards_in: int = 0
    discards_out: int = 0
    speed_bps: Optional[int] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class DevicePollResult:
    """Outcome of a single polling cycle against a remote device target."""

    device_id: str
    success: bool
    reachability: str  # configured, reachable, unreachable, unsupported
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    interfaces: List[RawInterfaceCounters] = field(default_factory=list)
    system_uptime: Optional[float] = None
    system_descr: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ComputedInterfaceMetrics:
    """Calculated rate metrics derived from counter differences across poll intervals."""

    interface_index: Optional[int]
    interface_name: str
    oper_status: str
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    upload_mbps: float
    download_mbps: float
    packets_sent_per_sec: float
    packets_recv_per_sec: float
    errors_in: int
    errors_out: int
    discards_in: int
    discards_out: int
    data_validity: str  # valid, initial_sample, counter_reset, mock, degraded, error
    timestamp: float


class BaseRemoteCollector(ABC):
    """Abstract interface for remote network telemetry collectors."""

    @abstractmethod
    async def poll(
        self,
        target_ip: str,
        device_id: str,
        timeout_seconds: float = 3.0,
    ) -> DevicePollResult:
        """Poll telemetry from a target IP address.

        Must never block the asyncio event loop and must safely handle connection
        failures, timeouts, and unsupported counters without raising uncaught exceptions.
        """
        raise NotImplementedError
