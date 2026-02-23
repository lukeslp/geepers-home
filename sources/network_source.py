"""Network health data source.

Reads local network information from the Pi:
- IP address (from socket)
- Ping latency to a configurable host (default: dr.eamer.dev)
- WiFi signal strength from /proc/net/wireless (if available)
- Interface stats (bytes rx/tx) from /proc/net/dev

No external dependencies beyond stdlib.

Config example:
    sources:
      - id: "net.health"
        type: "network"
        interval: 30
        ping_host: "dr.eamer.dev"
"""

import logging
import os
import socket
import subprocess
import time
from typing import Any, Dict, Optional

from core.data_source import DataSource
from core.registry import register_source

logger = logging.getLogger(__name__)


@register_source("network")
class NetworkSource(DataSource):
    """Reads Pi network health metrics."""

    def __init__(self, source_id: str, bus, config: Dict):
        config.setdefault("interval", 30.0)
        super().__init__(source_id, bus, config)
        self._ping_host = config.get("ping_host", "dr.eamer.dev")
        self._last_rx = 0
        self._last_tx = 0
        self._last_time = 0

    def fetch(self) -> Optional[Dict[str, Any]]:
        data = {}

        # IP address
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            data["ip"] = s.getsockname()[0]
            s.close()
        except Exception:
            data["ip"] = "No network"

        # Hostname
        try:
            data["hostname"] = socket.gethostname()
        except Exception:
            data["hostname"] = "?"

        # Ping latency
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "3", self._ping_host],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                # Parse "time=12.3 ms"
                for part in result.stdout.split():
                    if part.startswith("time="):
                        data["ping_ms"] = float(part.split("=")[1])
                        break
            else:
                data["ping_ms"] = -1
        except Exception:
            data["ping_ms"] = -1

        # WiFi signal from /proc/net/wireless
        try:
            with open("/proc/net/wireless") as f:
                lines = f.readlines()
            if len(lines) > 2:
                parts = lines[2].split()
                data["wifi_interface"] = parts[0].rstrip(":")
                data["wifi_signal"] = float(parts[3].rstrip("."))
                data["wifi_noise"] = float(parts[4].rstrip("."))
                # Convert to rough percentage (signal is dBm, typical -90 to -20)
                sig = data["wifi_signal"]
                data["wifi_pct"] = max(0, min(100, (sig + 90) * (100 / 70)))
            else:
                data["wifi_pct"] = -1
        except (FileNotFoundError, IndexError, ValueError):
            data["wifi_pct"] = -1

        # Interface throughput from /proc/net/dev
        now = time.time()
        try:
            with open("/proc/net/dev") as f:
                lines = f.readlines()
            total_rx, total_tx = 0, 0
            for line in lines[2:]:
                parts = line.split()
                iface = parts[0].rstrip(":")
                if iface == "lo":
                    continue
                total_rx += int(parts[1])
                total_tx += int(parts[9])

            if self._last_time > 0:
                dt = now - self._last_time
                if dt > 0:
                    data["rx_kbps"] = ((total_rx - self._last_rx) / 1024) / dt
                    data["tx_kbps"] = ((total_tx - self._last_tx) / 1024) / dt
                else:
                    data["rx_kbps"] = 0
                    data["tx_kbps"] = 0
            else:
                data["rx_kbps"] = 0
                data["tx_kbps"] = 0

            self._last_rx = total_rx
            self._last_tx = total_tx
            self._last_time = now
        except Exception:
            data["rx_kbps"] = 0
            data["tx_kbps"] = 0

        # Active connections count
        try:
            result = subprocess.run(
                ["ss", "-tun", "state", "established"],
                capture_output=True, text=True, timeout=3,
            )
            # Subtract 1 for header line
            data["connections"] = max(0, len(result.stdout.strip().split("\n")) - 1)
        except Exception:
            data["connections"] = 0

        return data
