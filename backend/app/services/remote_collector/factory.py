"""Factory and registration for remote device telemetry collectors."""

from typing import Dict
from app.services.remote_collector.base import BaseRemoteCollector
from app.services.remote_collector.mock_collector import MockRemoteCollector
from app.services.remote_collector.psutil_adapter import LocalPsutilAdapter
from app.services.remote_collector.snmp_collector import SNMPv2cCollector, SNMPv3Collector


class RemoteCollectorFactory:
    """Provides appropriate collector implementation according to device configuration."""

    def __init__(self) -> None:
        self._collectors: Dict[str, BaseRemoteCollector] = {
            "mock": MockRemoteCollector(),
            "manual": MockRemoteCollector(),  # safe mock telemetry for manual test devices
            "snmp": SNMPv2cCollector(),
            "snmp_v2c": SNMPv2cCollector(),
            "snmp_v3": SNMPv3Collector(),
            "local_psutil": LocalPsutilAdapter(),
        }

    def get_collector(self, collection_method: str) -> BaseRemoteCollector:
        """Retrieve collector instance for the designated method, falling back to mock."""
        clean_method = (collection_method or "mock").strip().lower()
        return self._collectors.get(clean_method, self._collectors["mock"])

    def register_collector(self, method: str, collector: BaseRemoteCollector) -> None:
        """Allow injecting custom or test collectors dynamically."""
        self._collectors[method.strip().lower()] = collector


collector_factory = RemoteCollectorFactory()
