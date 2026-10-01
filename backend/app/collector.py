"""Network Traffic Collector module.

Collects real-time network traffic statistics from network interfaces
using psutil, calculating throughput, packet rates, and data volume without
requiring packet-level inspection or administrative privileges.
"""

from dataclasses import dataclass
import time
from typing import Callable, Dict, List, Optional
import psutil


class NetworkCollectorError(Exception):
    """Base exception for network traffic collector errors."""


class InterfaceNotFoundError(NetworkCollectorError):
    """Raised when the requested network interface cannot be found."""


class CountersUnavailableError(NetworkCollectorError):
    """Raised when network I/O counters cannot be retrieved from the OS."""


@dataclass(frozen=True)
class RawInterfaceSample:
    """Raw snapshot of network interface counters at a point in time."""

    timestamp: float
    wall_time: float
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errin: int = 0
    errout: int = 0
    dropin: int = 0
    dropout: int = 0


@dataclass(frozen=True)
class NetworkMetrics:
    """Computed network traffic metrics for a measurement interval."""

    interface_name: str
    timestamp: float
    elapsed_seconds: float

    # Real-time rates
    upload_mbps: float
    download_mbps: float
    packets_sent_per_sec: float
    packets_recv_per_sec: float

    # Session statistics (since collector started for this interface)
    session_bytes_sent: int
    session_bytes_recv: int
    session_transferred_mb: float

    # Cumulative OS counters (lifetime of interface since boot)
    cumulative_bytes_sent: int
    cumulative_bytes_recv: int
    cumulative_packets_sent: int
    cumulative_packets_recv: int
    cumulative_transferred_mb: float

    # Error and drop counters
    errin: int = 0
    errout: int = 0
    dropin: int = 0
    dropout: int = 0

    # Status flag
    is_initial_sample: bool = False


class NetworkTrafficCollector:
    """Collects and calculates real-time network traffic metrics for interfaces."""

    BYTES_IN_MEGABYTE = 1024 * 1024
    BITS_PER_BYTE = 8
    BITS_IN_MEGABIT = 1_000_000.0

    def __init__(
        self,
        io_counters_fn: Optional[Callable[..., Dict[str, any]]] = None,
        time_fn: Optional[Callable[[], float]] = None,
        wall_time_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        """Initialize the network traffic collector.

        Args:
            io_counters_fn: Optional callable to get network I/O counters
                (defaults to psutil.net_io_counters).
            time_fn: Optional callable returning monotonic time in seconds
                (defaults to time.monotonic).
            wall_time_fn: Optional callable returning wall-clock epoch time
                (defaults to time.time).
        """
        self._io_counters_fn = io_counters_fn or psutil.net_io_counters
        self._time_fn = time_fn or time.monotonic
        self._wall_time_fn = wall_time_fn or time.time

        self._previous_samples: Dict[str, RawInterfaceSample] = {}
        self._baseline_samples: Dict[str, RawInterfaceSample] = {}

    def get_available_interfaces(self) -> List[str]:
        """Detect and return all available network interface names.

        Returns:
            List of network interface names present on the system.

        Raises:
            CountersUnavailableError: If the OS fails to return network counters.
        """
        try:
            counters = self._io_counters_fn(pernic=True)
        except Exception as exc:
            raise CountersUnavailableError(
                f"Failed to query network I/O counters: {exc}"
            ) from exc

        if counters is None:
            raise CountersUnavailableError("Network I/O counters are unavailable.")

        return sorted(counters.keys())

    def get_raw_sample(self, interface_name: str) -> RawInterfaceSample:
        """Fetch raw cumulative counters for a specific network interface.

        Args:
            interface_name: Name of the network interface.

        Returns:
            RawInterfaceSample containing raw byte and packet counts.

        Raises:
            InterfaceNotFoundError: If the interface is not in the counter list.
            CountersUnavailableError: If counters cannot be queried.
        """
        try:
            counters = self._io_counters_fn(pernic=True)
        except Exception as exc:
            raise CountersUnavailableError(
                f"Failed to query network I/O counters: {exc}"
            ) from exc

        if counters is None:
            raise CountersUnavailableError("Network I/O counters are unavailable.")

        if interface_name not in counters:
            available = ", ".join(sorted(counters.keys()))
            raise InterfaceNotFoundError(
                f"Interface '{interface_name}' not found. Available interfaces: [{available}]"
            )

        nic_data = counters[interface_name]
        return RawInterfaceSample(
            timestamp=self._time_fn(),
            wall_time=self._wall_time_fn(),
            bytes_sent=nic_data.bytes_sent,
            bytes_recv=nic_data.bytes_recv,
            packets_sent=nic_data.packets_sent,
            packets_recv=nic_data.packets_recv,
            errin=getattr(nic_data, "errin", 0),
            errout=getattr(nic_data, "errout", 0),
            dropin=getattr(nic_data, "dropin", 0),
            dropout=getattr(nic_data, "dropout", 0),
        )

    def collect(self, interface_name: str) -> NetworkMetrics:
        """Collect current statistics and calculate network rates for an interface.

        Handles:
            - Safe first sample baseline (zero rates).
            - Zero or negative elapsed time without division by zero.
            - Counter resets / rollbacks without negative values.
            - Accurate Mbps and packet rates based on actual elapsed time.

        Args:
            interface_name: The interface to monitor.

        Returns:
            NetworkMetrics with throughput and packet rates.

        Raises:
            InterfaceNotFoundError: If interface is not present.
            CountersUnavailableError: If counters cannot be queried.
        """
        current_sample = self.get_raw_sample(interface_name)
        prev_sample = self._previous_samples.get(interface_name)
        baseline_sample = self._baseline_samples.get(interface_name)

        # First sample initialization
        if prev_sample is None or baseline_sample is None:
            self._previous_samples[interface_name] = current_sample
            self._baseline_samples[interface_name] = current_sample

            cumulative_mb = (
                (current_sample.bytes_sent + current_sample.bytes_recv)
                / self.BYTES_IN_MEGABYTE
            )

            return NetworkMetrics(
                interface_name=interface_name,
                timestamp=current_sample.wall_time,
                elapsed_seconds=0.0,
                upload_mbps=0.0,
                download_mbps=0.0,
                packets_sent_per_sec=0.0,
                packets_recv_per_sec=0.0,
                session_bytes_sent=0,
                session_bytes_recv=0,
                session_transferred_mb=0.0,
                cumulative_bytes_sent=current_sample.bytes_sent,
                cumulative_bytes_recv=current_sample.bytes_recv,
                cumulative_packets_sent=current_sample.packets_sent,
                cumulative_packets_recv=current_sample.packets_recv,
                cumulative_transferred_mb=round(cumulative_mb, 2),
                errin=current_sample.errin,
                errout=current_sample.errout,
                dropin=current_sample.dropin,
                dropout=current_sample.dropout,
                is_initial_sample=True,
            )

        elapsed_seconds = current_sample.timestamp - prev_sample.timestamp

        # Detect counter reset or decrement (e.g. NIC reconnect, reboot, overflow)
        is_counter_reset = (
            current_sample.bytes_sent < prev_sample.bytes_sent
            or current_sample.bytes_recv < prev_sample.bytes_recv
            or current_sample.packets_sent < prev_sample.packets_sent
            or current_sample.packets_recv < prev_sample.packets_recv
        )

        if is_counter_reset:
            # Re-baseline session to current sample to prevent negative numbers
            self._baseline_samples[interface_name] = current_sample
            baseline_sample = current_sample
            delta_bytes_sent = 0
            delta_bytes_recv = 0
            delta_packets_sent = 0
            delta_packets_recv = 0
        else:
            delta_bytes_sent = current_sample.bytes_sent - prev_sample.bytes_sent
            delta_bytes_recv = current_sample.bytes_recv - prev_sample.bytes_recv
            delta_packets_sent = (
                current_sample.packets_sent - prev_sample.packets_sent
            )
            delta_packets_recv = (
                current_sample.packets_recv - prev_sample.packets_recv
            )

        # Safe rate calculation guarding against zero or negative elapsed time
        if elapsed_seconds <= 0.0 or is_counter_reset:
            upload_mbps = 0.0
            download_mbps = 0.0
            packets_sent_per_sec = 0.0
            packets_recv_per_sec = 0.0
        else:
            upload_mbps = (
                (delta_bytes_sent * self.BITS_PER_BYTE)
                / (self.BITS_IN_MEGABIT * elapsed_seconds)
            )
            download_mbps = (
                (delta_bytes_recv * self.BITS_PER_BYTE)
                / (self.BITS_IN_MEGABIT * elapsed_seconds)
            )
            packets_sent_per_sec = delta_packets_sent / elapsed_seconds
            packets_recv_per_sec = delta_packets_recv / elapsed_seconds

        # Update previous sample pointer
        self._previous_samples[interface_name] = current_sample

        # Session transferred bytes
        session_sent = max(0, current_sample.bytes_sent - baseline_sample.bytes_sent)
        session_recv = max(0, current_sample.bytes_recv - baseline_sample.bytes_recv)
        session_transferred_mb = (session_sent + session_recv) / self.BYTES_IN_MEGABYTE

        cumulative_mb = (
            (current_sample.bytes_sent + current_sample.bytes_recv)
            / self.BYTES_IN_MEGABYTE
        )

        return NetworkMetrics(
            interface_name=interface_name,
            timestamp=current_sample.wall_time,
            elapsed_seconds=max(0.0, elapsed_seconds),
            upload_mbps=round(max(0.0, upload_mbps), 4),
            download_mbps=round(max(0.0, download_mbps), 4),
            packets_sent_per_sec=round(max(0.0, packets_sent_per_sec), 2),
            packets_recv_per_sec=round(max(0.0, packets_recv_per_sec), 2),
            session_bytes_sent=session_sent,
            session_bytes_recv=session_recv,
            session_transferred_mb=round(session_transferred_mb, 3),
            cumulative_bytes_sent=current_sample.bytes_sent,
            cumulative_bytes_recv=current_sample.bytes_recv,
            cumulative_packets_sent=current_sample.packets_sent,
            cumulative_packets_recv=current_sample.packets_recv,
            cumulative_transferred_mb=round(cumulative_mb, 2),
            errin=current_sample.errin,
            errout=current_sample.errout,
            dropin=current_sample.dropin,
            dropout=current_sample.dropout,
            is_initial_sample=False,
        )

    def reset(self, interface_name: Optional[str] = None) -> None:
        """Reset internal state.

        Args:
            interface_name: If specified, reset only that interface.
                If None, reset all interfaces.
        """
        if interface_name:
            self._previous_samples.pop(interface_name, None)
            self._baseline_samples.pop(interface_name, None)
        else:
            self._previous_samples.clear()
            self._baseline_samples.clear()
