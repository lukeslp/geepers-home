"""WiFi scanner data source for Home Station.

Scans nearby WiFi access points using `iw` and publishes
network count, strongest signal, and connected network info.
"""

import logging
import re
import subprocess
from typing import Any, Dict, Optional

from core.data_source import DataSource
from core.registry import register_source

logger = logging.getLogger(__name__)


@register_source("wifi_scanner")
class WiFiScannerSource(DataSource):
    """Scans WiFi networks via `sudo iw dev <iface> scan`."""

    def __init__(self, source_id, bus, config):
        super().__init__(source_id, bus, config)
        self.interface = config.get("interface", "wlan0")
        self.interval = config.get("interval", 60)
        self._demo = config.get("demo", False)

    def fetch(self) -> Optional[Dict[str, Any]]:
        if self._demo:
            return self._simulate()
        return self._scan()

    def _scan(self) -> Dict[str, Any]:
        """Run iw scan and parse results."""
        # Try full AP scan first
        try:
            result = subprocess.run(
                ["sudo", "/usr/sbin/iw", "dev", self.interface, "scan"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                return self._parse_iw_scan(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.warning("iw scan failed: %s", exc)

        # Fallback: connected network only via /proc/net/wireless
        return self._fallback_proc()

    def _parse_iw_scan(self, output: str) -> Dict[str, Any]:
        """Parse `iw dev wlan0 scan` output into structured data."""
        networks = []
        current = {}

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("BSS "):
                if current:
                    networks.append(current)
                mac = line.split()[1].rstrip("(")
                current = {"mac": mac, "signal": -100, "ssid": "", "freq": 0}
            elif line.startswith("SSID:"):
                current["ssid"] = line[5:].strip()
            elif line.startswith("signal:"):
                match = re.search(r"(-?\d+\.?\d*)", line)
                if match:
                    current["signal"] = float(match.group(1))
            elif line.startswith("freq:"):
                match = re.search(r"(\d+)", line)
                if match:
                    current["freq"] = int(match.group(1))

        if current:
            networks.append(current)

        # Filter out hidden networks (empty SSID)
        visible = [n for n in networks if n.get("ssid")]

        # Find strongest
        strongest = max(visible, key=lambda n: n["signal"]) if visible else None

        # Find connected network
        connected = self._get_connected()

        data = {
            "network_count": len(visible),
            "strongest_ssid": strongest["ssid"] if strongest else "",
            "strongest_signal": strongest["signal"] if strongest else -100,
        }

        if connected:
            data["connected_ssid"] = connected.get("ssid", "")
            data["connected_signal"] = connected.get("signal", -100)
            data["channel"] = connected.get("channel", 0)
        else:
            data["connected_ssid"] = ""
            data["connected_signal"] = -100
            data["channel"] = 0

        return data

    def _get_connected(self) -> Optional[Dict[str, Any]]:
        """Get currently connected network info via iw link."""
        try:
            result = subprocess.run(
                ["/usr/sbin/iw", "dev", self.interface, "link"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0 or "Not connected" in result.stdout:
                return None

            info = {}
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("SSID:"):
                    info["ssid"] = line[5:].strip()
                elif line.startswith("signal:"):
                    match = re.search(r"(-?\d+)", line)
                    if match:
                        info["signal"] = int(match.group(1))
                elif line.startswith("freq:"):
                    match = re.search(r"(\d+)", line)
                    if match:
                        # Convert frequency to channel (rough)
                        freq = int(match.group(1))
                        if 2412 <= freq <= 2484:
                            info["channel"] = (freq - 2407) // 5
                        elif 5170 <= freq <= 5825:
                            info["channel"] = (freq - 5000) // 5
                        else:
                            info["channel"] = 0
            return info if info else None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def _fallback_proc(self) -> Dict[str, Any]:
        """Fallback: read /proc/net/wireless for connected signal only."""
        data = {
            "network_count": 0,
            "strongest_ssid": "",
            "strongest_signal": -100,
            "connected_ssid": "",
            "connected_signal": -100,
            "channel": 0,
        }
        try:
            with open("/proc/net/wireless") as f:
                lines = f.readlines()
            for line in lines[2:]:  # Skip header lines
                parts = line.split()
                if len(parts) >= 4:
                    iface = parts[0].rstrip(":")
                    if iface == self.interface:
                        # Quality is in column 2, signal in column 3
                        signal = float(parts[3].rstrip("."))
                        data["connected_signal"] = signal
                        data["network_count"] = 1
                        # Get SSID from iwgetid
                        try:
                            r = subprocess.run(
                                ["iwgetid", self.interface, "--raw"],
                                capture_output=True, text=True, timeout=3
                            )
                            if r.returncode == 0:
                                data["connected_ssid"] = r.stdout.strip()
                                data["strongest_ssid"] = r.stdout.strip()
                                data["strongest_signal"] = signal
                        except (subprocess.TimeoutExpired, FileNotFoundError):
                            pass
        except (OSError, IndexError, ValueError) as exc:
            logger.debug("proc wireless fallback failed: %s", exc)

        return data

    def _simulate(self) -> Dict[str, Any]:
        """Demo mode: return simulated WiFi scan data."""
        import random
        networks = random.randint(5, 25)
        return {
            "network_count": networks,
            "strongest_ssid": "HomeNetwork-5G",
            "strongest_signal": random.randint(-45, -25),
            "connected_ssid": "HomeNetwork-5G",
            "connected_signal": random.randint(-55, -35),
            "channel": random.choice([1, 6, 11, 36, 44, 149]),
        }
