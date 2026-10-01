"""Runner script for real-time network traffic collection.

Allows selecting an interface, collects real-time metrics using
NetworkTrafficCollector, displays human-readable output every second,
and terminates gracefully on SIGINT (Ctrl+C).
"""

import argparse
import sys
import time
from typing import Optional

# Allow running directly from repo root or backend folder
from app.collector import (
    CountersUnavailableError,
    InterfaceNotFoundError,
    NetworkCollectorError,
    NetworkTrafficCollector,
)


def format_traffic_summary(metrics) -> str:
    """Format a single sample line for console display."""
    time_str = time.strftime("%H:%M:%S", time.localtime(metrics.timestamp))
    return (
        f"{time_str} | "
        f"Up: {metrics.upload_mbps:>8.3f} Mbps | "
        f"Down: {metrics.download_mbps:>8.3f} Mbps | "
        f"Tx: {metrics.packets_sent_per_sec:>6.1f} pkt/s | "
        f"Rx: {metrics.packets_recv_per_sec:>6.1f} pkt/s | "
        f"Session: {metrics.session_transferred_mb:>7.2f} MB | "
        f"Total: {metrics.cumulative_transferred_mb:>8.1f} MB"
    )


def select_interface_interactive(interfaces: list[str]) -> str:
    """Prompt the user to select an interface from the available list."""
    print("\nAvailable Network Interfaces:")
    print("=" * 60)
    for idx, iface in enumerate(interfaces, start=1):
        print(f"  [{idx}] {iface}")
    print("=" * 60)

    while True:
        try:
            choice = input(f"\nSelect interface [1-{len(interfaces)}] (or 'q' to quit): ").strip()
            if choice.lower() in ("q", "quit", "exit"):
                print("Exiting...")
                sys.exit(0)

            if not choice:
                print("Please enter a valid choice.")
                continue

            # If user entered the exact name
            if choice in interfaces:
                return choice

            # If user entered index
            idx_choice = int(choice)
            if 1 <= idx_choice <= len(interfaces):
                return interfaces[idx_choice - 1]
            else:
                print(f"Error: Choice must be between 1 and {len(interfaces)}.")
        except ValueError:
            print("Error: Please enter a valid number or exact interface name.")


def run_monitoring_loop(
    collector: NetworkTrafficCollector,
    interface_name: str,
    interval_seconds: float = 1.0,
    max_samples: Optional[int] = None,
) -> None:
    """Run the traffic collection loop until interrupted or max_samples reached."""
    print("\n" + "=" * 80)
    print(f"  Smart Network Monitoring AI - Real-Time Collector")
    print(f"  Interface : {interface_name}")
    print(f"  Interval  : {interval_seconds:.1f}s")
    print(f"  Status    : Active (Press Ctrl+C to stop)")
    print("=" * 80)
    header = (
        f"{'Time':^8} | "
        f"{'Upload Rate':^16} | "
        f"{'Download Rate':^16} | "
        f"{'Packet Tx':^13} | "
        f"{'Packet Rx':^13} | "
        f"{'Session':^13} | "
        f"{'Lifetime':^14}"
    )
    print(header)
    print("-" * 80)

    sample_count = 0
    start_time = time.monotonic()
    peak_upload = 0.0
    peak_download = 0.0
    last_metrics = None

    try:
        while True:
            metrics = collector.collect(interface_name)
            last_metrics = metrics

            if not metrics.is_initial_sample:
                peak_upload = max(peak_upload, metrics.upload_mbps)
                peak_download = max(peak_download, metrics.download_mbps)
                print(format_traffic_summary(metrics))
            else:
                time_str = time.strftime("%H:%M:%S", time.localtime(metrics.timestamp))
                print(
                    f"{time_str} | Initializing baseline counters for {interface_name}..."
                )

            sample_count += 1
            if max_samples and sample_count >= max_samples:
                break

            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\n\n" + "-" * 80)
        print("Monitoring stopped by user (Ctrl+C).")
    finally:
        total_duration = time.monotonic() - start_time
        print("\nSession Summary:")
        print("=" * 40)
        print(f"  Target Interface    : {interface_name}")
        print(f"  Monitoring Duration : {total_duration:.1f} seconds")
        print(f"  Total Samples       : {sample_count}")
        print(f"  Peak Upload Rate    : {peak_upload:.3f} Mbps")
        print(f"  Peak Download Rate  : {peak_download:.3f} Mbps")
        if last_metrics:
            print(f"  Session Transferred : {last_metrics.session_transferred_mb:.3f} MB")
            print(f"  Lifetime Total      : {last_metrics.cumulative_transferred_mb:.1f} MB")
        print("=" * 40)


def main() -> None:
    """Entry point for the network collector runner CLI."""
    parser = argparse.ArgumentParser(
        description="Smart Network Monitoring AI - Real-time Network Traffic Collector"
    )
    parser.add_argument(
        "-i",
        "--interface",
        type=str,
        default=None,
        help="Network interface name to monitor (skips prompt if valid)",
    )
    parser.add_argument(
        "-t",
        "--interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds (default: 1.0)",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List available network interfaces and exit",
    )
    parser.add_argument(
        "-n",
        "--samples",
        type=int,
        default=None,
        help="Number of samples to collect before exiting (default: run indefinitely)",
    )

    args = parser.parse_args()

    collector = NetworkTrafficCollector()

    try:
        interfaces = collector.get_available_interfaces()
    except CountersUnavailableError as exc:
        print(f"Error: Unable to access network counters on this machine: {exc}", file=sys.stderr)
        sys.exit(1)

    if not interfaces:
        print("Error: No network interfaces detected on this machine.", file=sys.stderr)
        sys.exit(1)

    if args.list:
        print("Detected Network Interfaces:")
        for idx, iface in enumerate(interfaces, start=1):
            print(f"  [{idx}] {iface}")
        sys.exit(0)

    selected_interface = args.interface

    if selected_interface:
        if selected_interface not in interfaces:
            print(
                f"Error: Interface '{selected_interface}' not found.\n"
                f"Available interfaces: {', '.join(interfaces)}",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        selected_interface = select_interface_interactive(interfaces)

    try:
        run_monitoring_loop(
            collector=collector,
            interface_name=selected_interface,
            interval_seconds=args.interval,
            max_samples=args.samples,
        )
    except (InterfaceNotFoundError, NetworkCollectorError) as exc:
        print(f"Collector Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
