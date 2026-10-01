"""Unit tests for the Network Traffic Collector module.

All tests use mocked network counters and synthetic time sources
to ensure tests are fast, deterministic, and independent of internet access.
"""

from collections import namedtuple
import pytest

from app.collector import (
    CountersUnavailableError,
    InterfaceNotFoundError,
    NetworkTrafficCollector,
)

# Mock structure identical to psutil._common.snetio
MockNetIO = namedtuple(
    "MockNetIO",
    [
        "bytes_sent",
        "bytes_recv",
        "packets_sent",
        "packets_recv",
        "errin",
        "errout",
        "dropin",
        "dropout",
    ],
    defaults=(0, 0, 0, 0),
)


class MockClock:
    """Controllable clock for monotonic and wall time in tests."""

    def __init__(self, initial_time: float = 1000.0) -> None:
        self.current_time = initial_time

    def time(self) -> float:
        return self.current_time

    def advance(self, seconds: float) -> None:
        self.current_time += seconds


class TestNetworkCollector:
    """Test suite for NetworkTrafficCollector."""

    def test_interface_discovery(self):
        """Verify successful detection of network interfaces."""
        mock_data = {
            "eth0": MockNetIO(bytes_sent=100, bytes_recv=200, packets_sent=5, packets_recv=10),
            "wlan0": MockNetIO(bytes_sent=300, bytes_recv=400, packets_sent=15, packets_recv=20),
        }
        collector = NetworkTrafficCollector(io_counters_fn=lambda pernic=True: mock_data)
        interfaces = collector.get_available_interfaces()

        assert interfaces == ["eth0", "wlan0"]

    def test_counters_unavailable_none(self):
        """Verify error when OS returns None for network counters."""
        collector = NetworkTrafficCollector(io_counters_fn=lambda pernic=True: None)
        with pytest.raises(CountersUnavailableError, match="unavailable"):
            collector.get_available_interfaces()

    def test_counters_unavailable_exception(self):
        """Verify error when OS raises exception during query."""
        def broken_io(pernic=True):
            raise PermissionError("Access denied by OS")

        collector = NetworkTrafficCollector(io_counters_fn=broken_io)
        with pytest.raises(CountersUnavailableError, match="Failed to query network I/O counters"):
            collector.get_available_interfaces()

    def test_missing_interface(self):
        """Verify error when querying an interface that does not exist."""
        mock_data = {
            "eth0": MockNetIO(bytes_sent=100, bytes_recv=200, packets_sent=5, packets_recv=10),
        }
        collector = NetworkTrafficCollector(io_counters_fn=lambda pernic=True: mock_data)

        with pytest.raises(InterfaceNotFoundError, match="Interface 'eth1' not found"):
            collector.collect("eth1")

    def test_first_measurement(self):
        """Verify first sample establishes baseline and reports 0 rates safely."""
        clock = MockClock(initial_time=100.0)
        mock_data = {
            "eth0": MockNetIO(
                bytes_sent=10_485_760,  # 10 MB
                bytes_recv=20_971_520,  # 20 MB
                packets_sent=5000,
                packets_recv=10000,
                errin=1,
                errout=2,
                dropin=3,
                dropout=4,
            ),
        }
        collector = NetworkTrafficCollector(
            io_counters_fn=lambda pernic=True: mock_data,
            time_fn=clock.time,
            wall_time_fn=clock.time,
        )

        metrics = collector.collect("eth0")

        assert metrics.is_initial_sample is True
        assert metrics.elapsed_seconds == 0.0
        assert metrics.upload_mbps == 0.0
        assert metrics.download_mbps == 0.0
        assert metrics.packets_sent_per_sec == 0.0
        assert metrics.packets_recv_per_sec == 0.0
        assert metrics.session_bytes_sent == 0
        assert metrics.session_bytes_recv == 0
        assert metrics.session_transferred_mb == 0.0
        assert metrics.cumulative_bytes_sent == 10_485_760
        assert metrics.cumulative_bytes_recv == 20_971_520
        assert metrics.cumulative_transferred_mb == pytest.approx(30.0, rel=1e-2)
        assert metrics.errin == 1
        assert metrics.errout == 2
        assert metrics.dropin == 3
        assert metrics.dropout == 4

    def test_normal_throughput_calculation(self):
        """Verify accurate upload, download Mbps and packet rate calculations."""
        clock = MockClock(initial_time=100.0)

        # Baseline sample: 0 bytes, 0 packets
        data_sample_1 = {
            "eth0": MockNetIO(
                bytes_sent=10_000_000,
                bytes_recv=20_000_000,
                packets_sent=1000,
                packets_recv=2000,
            )
        }
        current_data = data_sample_1

        collector = NetworkTrafficCollector(
            io_counters_fn=lambda pernic=True: current_data,
            time_fn=clock.time,
            wall_time_fn=clock.time,
        )

        # 1st sample establishes baseline
        collector.collect("eth0")

        # Advance 2 seconds
        clock.advance(2.0)

        # 2nd sample:
        # In 2 seconds:
        # Upload delta: 250,000 bytes -> 2,000,000 bits / 2s = 1.0 Mbps
        # Download delta: 1,000,000 bytes -> 8,000,000 bits / 2s = 4.0 Mbps
        # Tx packets delta: 200 packets / 2s = 100.0 pkts/s
        # Rx packets delta: 400 packets / 2s = 200.0 pkts/s
        current_data = {
            "eth0": MockNetIO(
                bytes_sent=10_000_000 + 250_000,
                bytes_recv=20_000_000 + 1_000_000,
                packets_sent=1000 + 200,
                packets_recv=2000 + 400,
            )
        }

        metrics = collector.collect("eth0")

        assert metrics.is_initial_sample is False
        assert metrics.elapsed_seconds == pytest.approx(2.0)
        assert metrics.upload_mbps == pytest.approx(1.0)
        assert metrics.download_mbps == pytest.approx(4.0)
        assert metrics.packets_sent_per_sec == pytest.approx(100.0)
        assert metrics.packets_recv_per_sec == pytest.approx(200.0)
        assert metrics.session_bytes_sent == 250_000
        assert metrics.session_bytes_recv == 1_000_000
        expected_session_mb = (250_000 + 1_000_000) / (1024 * 1024)
        assert metrics.session_transferred_mb == pytest.approx(expected_session_mb, rel=1e-3)

    def test_counter_reset_recovery(self):
        """Verify handling of counter decreases (NIC reset / reboot / counter wrap)."""
        clock = MockClock(initial_time=100.0)
        current_data = {
            "eth0": MockNetIO(
                bytes_sent=50_000_000,
                bytes_recv=50_000_000,
                packets_sent=50_000,
                packets_recv=50_000,
            )
        }
        collector = NetworkTrafficCollector(
            io_counters_fn=lambda pernic=True: current_data,
            time_fn=clock.time,
            wall_time_fn=clock.time,
        )

        # Baseline
        collector.collect("eth0")

        # Advance 1 second, but counters drop to 1000 bytes (NIC reset)
        clock.advance(1.0)
        current_data = {
            "eth0": MockNetIO(
                bytes_sent=1000,
                bytes_recv=2000,
                packets_sent=10,
                packets_recv=20,
            )
        }

        reset_metrics = collector.collect("eth0")

        # Must never output negative rates
        assert reset_metrics.upload_mbps == 0.0
        assert reset_metrics.download_mbps == 0.0
        assert reset_metrics.packets_sent_per_sec == 0.0
        assert reset_metrics.packets_recv_per_sec == 0.0
        assert reset_metrics.session_bytes_sent == 0
        assert reset_metrics.session_bytes_recv == 0

        # Next sample after reset should measure cleanly from new baseline
        clock.advance(1.0)
        current_data = {
            "eth0": MockNetIO(
                bytes_sent=1000 + 125_000,  # 1.0 Mbps
                bytes_recv=2000 + 250_000,  # 2.0 Mbps
                packets_sent=10 + 50,
                packets_recv=20 + 80,
            )
        }

        post_reset_metrics = collector.collect("eth0")
        assert post_reset_metrics.upload_mbps == pytest.approx(1.0)
        assert post_reset_metrics.download_mbps == pytest.approx(2.0)
        assert post_reset_metrics.packets_sent_per_sec == pytest.approx(50.0)
        assert post_reset_metrics.packets_recv_per_sec == pytest.approx(80.0)

    def test_zero_elapsed_time(self):
        """Verify zero elapsed time between calls does not divide by zero."""
        clock = MockClock(initial_time=100.0)
        current_data = {
            "eth0": MockNetIO(
                bytes_sent=1000,
                bytes_recv=1000,
                packets_sent=10,
                packets_recv=10,
            )
        }
        collector = NetworkTrafficCollector(
            io_counters_fn=lambda pernic=True: current_data,
            time_fn=clock.time,
            wall_time_fn=clock.time,
        )

        collector.collect("eth0")

        # Call again immediately with zero clock advance
        metrics = collector.collect("eth0")

        assert metrics.elapsed_seconds == 0.0
        assert metrics.upload_mbps == 0.0
        assert metrics.download_mbps == 0.0
        assert metrics.packets_sent_per_sec == 0.0
        assert metrics.packets_recv_per_sec == 0.0

    def test_negative_elapsed_time(self):
        """Verify non-monotonic clock adjustment (backwards in time) is handled safely."""
        clock = MockClock(initial_time=100.0)
        current_data = {
            "eth0": MockNetIO(
                bytes_sent=1000,
                bytes_recv=1000,
                packets_sent=10,
                packets_recv=10,
            )
        }
        collector = NetworkTrafficCollector(
            io_counters_fn=lambda pernic=True: current_data,
            time_fn=clock.time,
            wall_time_fn=clock.time,
        )

        collector.collect("eth0")

        # Clock stepped backward by 5 seconds
        clock.advance(-5.0)
        metrics = collector.collect("eth0")

        assert metrics.elapsed_seconds == 0.0
        assert metrics.upload_mbps == 0.0
        assert metrics.download_mbps == 0.0

    def test_collector_reset(self):
        """Verify that resetting collector state treats subsequent sample as initial."""
        clock = MockClock(initial_time=100.0)
        current_data = {
            "eth0": MockNetIO(
                bytes_sent=1000,
                bytes_recv=1000,
                packets_sent=10,
                packets_recv=10,
            )
        }
        collector = NetworkTrafficCollector(
            io_counters_fn=lambda pernic=True: current_data,
            time_fn=clock.time,
            wall_time_fn=clock.time,
        )

        m1 = collector.collect("eth0")
        assert m1.is_initial_sample is True

        clock.advance(1.0)
        current_data["eth0"] = MockNetIO(
            bytes_sent=2000,
            bytes_recv=2000,
            packets_sent=20,
            packets_recv=20,
        )
        m2 = collector.collect("eth0")
        assert m2.is_initial_sample is False

        # Reset state
        collector.reset()

        m3 = collector.collect("eth0")
        assert m3.is_initial_sample is True
        assert m3.upload_mbps == 0.0
