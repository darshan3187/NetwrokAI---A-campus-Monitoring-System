"""Network feature extraction module for AI anomaly detection.

Transforms raw network telemetry (throughput, packet rates, cumulative bytes) into
statistical and ratio-based feature vectors suitable for machine learning models.
Handles edge cases including initial baseline samples, zero-traffic conditions,
division by zero, and interface switching without injecting artificial measurements.
"""

from collections import deque
from dataclasses import dataclass, field
import math
from typing import Deque, Dict, List, Optional, Union
import numpy as np

from app.collector import NetworkMetrics


@dataclass
class NetworkFeatures:
    """Extracted feature representation for a single network telemetry observation."""

    download_mbps: float
    upload_mbps: float
    total_mbps: float
    packets_recv_per_sec: float
    packets_sent_per_sec: float
    total_packets_per_sec: float
    upload_download_ratio: float
    packet_ratio: float
    bytes_per_packet: float
    rolling_mean_mbps: float
    rolling_std_mbps: float
    mbps_deviation: float
    rolling_mean_packets: float
    rolling_std_packets: float
    packets_deviation: float

    # Ordered list of feature names for model interpretability and inspection
    FEATURE_NAMES = (
        "download_mbps",
        "upload_mbps",
        "total_mbps",
        "packets_recv_per_sec",
        "packets_sent_per_sec",
        "total_packets_per_sec",
        "upload_download_ratio",
        "packet_ratio",
        "bytes_per_packet",
        "rolling_mean_mbps",
        "rolling_std_mbps",
        "mbps_deviation",
        "rolling_mean_packets",
        "rolling_std_packets",
        "packets_deviation",
    )

    def to_vector(self) -> List[float]:
        """Return the numerical feature vector in canonical feature order."""
        return [
            self.download_mbps,
            self.upload_mbps,
            self.total_mbps,
            self.packets_recv_per_sec,
            self.packets_sent_per_sec,
            self.total_packets_per_sec,
            self.upload_download_ratio,
            self.packet_ratio,
            self.bytes_per_packet,
            self.rolling_mean_mbps,
            self.rolling_std_mbps,
            self.mbps_deviation,
            self.rolling_mean_packets,
            self.rolling_std_packets,
            self.packets_deviation,
        ]

    def to_numpy(self) -> np.ndarray:
        """Convert feature vector to a 2D numpy array suitable for scikit-learn models (1, n_features)."""
        return np.array([self.to_vector()], dtype=np.float32)

    def to_dict(self) -> Dict[str, float]:
        """Convert features to a readable dictionary for snapshots and logging."""
        return {
            name: round(val, 4)
            for name, val in zip(self.FEATURE_NAMES, self.to_vector())
        }


class NetworkFeatureExtractor:
    """Extracts statistical and temporal features from streaming network telemetry samples.

    Maintains a rolling window of recent measurements per interface to compute baseline
    averages, standard deviations, and relative deviations without storing unbounded history.
    """

    def __init__(self, window_size: int = 30) -> None:
        self.window_size = max(5, window_size)
        self.active_interface: Optional[str] = None
        self._history_mbps: Deque[float] = deque(maxlen=self.window_size)
        self._history_packets: Deque[float] = deque(maxlen=self.window_size)

    def reset(self, interface: Optional[str] = None) -> None:
        """Clear rolling history buffers, typically invoked when switching monitored adapters."""
        self._history_mbps.clear()
        self._history_packets.clear()
        self.active_interface = interface

    @property
    def history_length(self) -> int:
        """Return current number of samples stored in rolling history."""
        return len(self._history_mbps)

    def extract(
        self,
        sample: Union[NetworkMetrics, dict, object],
    ) -> NetworkFeatures:
        """Extract multi-dimensional feature vector from a single telemetry sample.

        Safely handles zero rates, missing fields, initial calibration ticks, and adapter transitions.
        """
        # Extract attributes from NetworkMetrics, NetworkMetricModel, or dict
        if isinstance(sample, dict):
            iface = str(sample.get("interface", sample.get("interface_name", "unknown")))
            dl_mbps = float(sample.get("download_mbps", 0.0))
            ul_mbps = float(sample.get("upload_mbps", 0.0))
            pkts_recv = float(sample.get("packets_received_per_sec", sample.get("packets_recv_per_sec", 0.0)))
            pkts_sent = float(sample.get("packets_sent_per_sec", 0.0))
            is_initial = bool(sample.get("is_initial_sample", False))
        else:
            iface = getattr(sample, "interface_name", getattr(sample, "interface", "unknown"))
            dl_mbps = float(getattr(sample, "download_mbps", 0.0))
            ul_mbps = float(getattr(sample, "upload_mbps", 0.0))
            pkts_recv = float(getattr(sample, "packets_recv_per_sec", getattr(sample, "packets_received_per_sec", 0.0)))
            pkts_sent = float(getattr(sample, "packets_sent_per_sec", 0.0))
            is_initial = bool(getattr(sample, "is_initial_sample", False))

        # Handle interface transition
        if self.active_interface is not None and iface != self.active_interface:
            self.reset(iface)
        elif self.active_interface is None:
            self.active_interface = iface

        # Clean numerical values (replace negative, NaN, or Inf with 0.0)
        dl_mbps = dl_mbps if (math.isfinite(dl_mbps) and dl_mbps >= 0.0) else 0.0
        ul_mbps = ul_mbps if (math.isfinite(ul_mbps) and ul_mbps >= 0.0) else 0.0
        pkts_recv = pkts_recv if (math.isfinite(pkts_recv) and pkts_recv >= 0.0) else 0.0
        pkts_sent = pkts_sent if (math.isfinite(pkts_sent) and pkts_sent >= 0.0) else 0.0

        total_mbps = dl_mbps + ul_mbps
        total_packets = pkts_recv + pkts_sent

        # Upload / Download throughput ratio with safe epsilon division
        # When both are zero, ratio is 1.0 (balanced idle state)
        if dl_mbps == 0.0 and ul_mbps == 0.0:
            up_down_ratio = 1.0
        else:
            up_down_ratio = ul_mbps / (dl_mbps + 1e-4)

        # Upload / Download packet count ratio
        if pkts_recv == 0.0 and pkts_sent == 0.0:
            packet_ratio = 1.0
        else:
            packet_ratio = pkts_sent / (pkts_recv + 1e-4)

        # Average bytes per packet (1 Mbps = 125,000 bytes/sec)
        total_bytes_per_sec = total_mbps * 125_000.0
        if total_packets > 0.0:
            bytes_per_packet = total_bytes_per_sec / total_packets
        else:
            bytes_per_packet = 0.0

        # Compute rolling baseline metrics before appending new sample if history exists
        if self._history_mbps:
            mbps_arr = np.array(self._history_mbps, dtype=np.float64)
            pkts_arr = np.array(self._history_packets, dtype=np.float64)

            mean_mbps = float(np.mean(mbps_arr))
            std_mbps = float(np.std(mbps_arr))
            mean_packets = float(np.mean(pkts_arr))
            std_packets = float(np.std(pkts_arr))

            # Z-score / standardized deviation from baseline
            mbps_deviation = abs(total_mbps - mean_mbps) / (std_mbps + 1e-4)
            packets_deviation = abs(total_packets - mean_packets) / (std_packets + 1e-4)
        else:
            mean_mbps = total_mbps
            std_mbps = 0.0
            mbps_deviation = 0.0
            mean_packets = total_packets
            std_packets = 0.0
            packets_deviation = 0.0

        # Append valid non-initial sample to rolling baseline history
        if not is_initial:
            self._history_mbps.append(total_mbps)
            self._history_packets.append(total_packets)

        return NetworkFeatures(
            download_mbps=round(dl_mbps, 4),
            upload_mbps=round(ul_mbps, 4),
            total_mbps=round(total_mbps, 4),
            packets_recv_per_sec=round(pkts_recv, 2),
            packets_sent_per_sec=round(pkts_sent, 2),
            total_packets_per_sec=round(total_packets, 2),
            upload_download_ratio=round(min(100.0, up_down_ratio), 4),
            packet_ratio=round(min(100.0, packet_ratio), 4),
            bytes_per_packet=round(bytes_per_packet, 2),
            rolling_mean_mbps=round(mean_mbps, 4),
            rolling_std_mbps=round(std_mbps, 4),
            mbps_deviation=round(min(100.0, mbps_deviation), 4),
            rolling_mean_packets=round(mean_packets, 2),
            rolling_std_packets=round(std_packets, 2),
            packets_deviation=round(min(100.0, packets_deviation), 4),
        )
