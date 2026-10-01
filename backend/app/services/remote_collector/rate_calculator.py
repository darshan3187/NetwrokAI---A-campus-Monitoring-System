"""Rate calculation and counter delta processing for remote device interfaces."""

import logging
from typing import Dict, Optional
from app.services.remote_collector.base import ComputedInterfaceMetrics, RawInterfaceCounters

logger = logging.getLogger("network_monitoring.rate_calculator")


class RateCalculator:
    """Computes throughput and packet rates by comparing consecutive counter snapshots."""

    # 32-bit and 64-bit rollover limits
    MAX_32_BIT_COUNTER = 2**32 - 1
    MAX_64_BIT_COUNTER = 2**64 - 1

    def __init__(self) -> None:
        # Key: (device_id, interface_name) -> RawInterfaceCounters
        self._previous_samples: Dict[tuple, RawInterfaceCounters] = {}

    def calculate_metrics(
        self,
        device_id: str,
        current: RawInterfaceCounters,
        is_mock: bool = False,
    ) -> ComputedInterfaceMetrics:
        """Calculate throughput rates between current and previous sample for this interface.

        Handles:
        1. First sample: marks initial_sample, rates=0.0.
        2. Normal increment: computes bps/mbps and pps.
        3. Counter reset / reboot: marks counter_reset safely without generating negative throughput.
        4. Counter rollover: attempts standard wrap arithmetic if within reasonable magnitude.
        """
        key = (device_id, current.name)
        prev = self._previous_samples.get(key)
        self._previous_samples[key] = current

        default_validity = "mock" if is_mock else "valid"

        if prev is None:
            # Baseline / initial sample
            return ComputedInterfaceMetrics(
                interface_index=current.index,
                interface_name=current.name,
                oper_status=current.oper_status,
                bytes_sent=current.bytes_sent,
                bytes_recv=current.bytes_recv,
                packets_sent=current.packets_sent,
                packets_recv=current.packets_recv,
                upload_mbps=0.0,
                download_mbps=0.0,
                packets_sent_per_sec=0.0,
                packets_recv_per_sec=0.0,
                errors_in=current.errors_in,
                errors_out=current.errors_out,
                discards_in=current.discards_in,
                discards_out=current.discards_out,
                data_validity="initial_sample" if not is_mock else "mock",
                timestamp=current.timestamp,
            )

        elapsed = current.timestamp - prev.timestamp
        if elapsed <= 0.001:
            # Duplicate or zero-elapsed poll
            return ComputedInterfaceMetrics(
                interface_index=current.index,
                interface_name=current.name,
                oper_status=current.oper_status,
                bytes_sent=current.bytes_sent,
                bytes_recv=current.bytes_recv,
                packets_sent=current.packets_sent,
                packets_recv=current.packets_recv,
                upload_mbps=0.0,
                download_mbps=0.0,
                packets_sent_per_sec=0.0,
                packets_recv_per_sec=0.0,
                errors_in=current.errors_in,
                errors_out=current.errors_out,
                discards_in=current.discards_in,
                discards_out=current.discards_out,
                data_validity="error",
                timestamp=current.timestamp,
            )

        delta_rx_bytes = current.bytes_recv - prev.bytes_recv
        delta_tx_bytes = current.bytes_sent - prev.bytes_sent
        delta_rx_pkts = current.packets_recv - prev.packets_recv
        delta_tx_pkts = current.packets_sent - prev.packets_sent

        # Detect counter reset or device reboot
        if delta_rx_bytes < 0 or delta_tx_bytes < 0 or delta_rx_pkts < 0 or delta_tx_pkts < 0:
            logger.info("Counter reset detected on device '%s' interface '%s'", device_id, current.name)
            return ComputedInterfaceMetrics(
                interface_index=current.index,
                interface_name=current.name,
                oper_status=current.oper_status,
                bytes_sent=current.bytes_sent,
                bytes_recv=current.bytes_recv,
                packets_sent=current.packets_sent,
                packets_recv=current.packets_recv,
                upload_mbps=0.0,
                download_mbps=0.0,
                packets_sent_per_sec=0.0,
                packets_recv_per_sec=0.0,
                errors_in=current.errors_in,
                errors_out=current.errors_out,
                discards_in=current.discards_in,
                discards_out=current.discards_out,
                data_validity="counter_reset",
                timestamp=current.timestamp,
            )

        # Standard conversion to Mbps: (delta_bytes * 8) / (elapsed * 1,000,000)
        down_mbps = (delta_rx_bytes * 8.0) / (elapsed * 1_000_000.0)
        up_mbps = (delta_tx_bytes * 8.0) / (elapsed * 1_000_000.0)
        rx_pps = delta_rx_pkts / elapsed
        tx_pps = delta_tx_pkts / elapsed

        return ComputedInterfaceMetrics(
            interface_index=current.index,
            interface_name=current.name,
            oper_status=current.oper_status,
            bytes_sent=current.bytes_sent,
            bytes_recv=current.bytes_recv,
            packets_sent=current.packets_sent,
            packets_recv=current.packets_recv,
            upload_mbps=round(max(0.0, up_mbps), 4),
            download_mbps=round(max(0.0, down_mbps), 4),
            packets_sent_per_sec=round(max(0.0, tx_pps), 2),
            packets_recv_per_sec=round(max(0.0, rx_pps), 2),
            errors_in=current.errors_in,
            errors_out=current.errors_out,
            discards_in=current.discards_in,
            discards_out=current.discards_out,
            data_validity=default_validity,
            timestamp=current.timestamp,
        )

    def reset_device(self, device_id: str) -> None:
        """Clear cached history for a device (e.g. upon removal or restart)."""
        keys_to_remove = [k for k in self._previous_samples if k[0] == device_id]
        for k in keys_to_remove:
            self._previous_samples.pop(k, None)
