"""Bluetooth scanner data source for Home Station.

Scans for nearby BLE and classic Bluetooth devices using
hcitool and publishes device counts.
"""

import logging
import re
import subprocess
from typing import Any, Dict, List, Optional

from core.data_source import DataSource
from core.registry import register_source

logger = logging.getLogger(__name__)


@register_source("bluetooth_scanner")
class BluetoothScannerSource(DataSource):
    """Scans Bluetooth devices via hcitool."""

    def __init__(self, source_id, bus, config):
        super().__init__(source_id, bus, config)
        self.interval = config.get("interval", 120)
        self._demo = config.get("demo", False)

    def fetch(self) -> Optional[Dict[str, Any]]:
        if self._demo:
            return self._simulate()
        return self._scan()

    def _scan(self) -> Dict[str, Any]:
        """Run BLE and classic scans, combine results."""
        # Reset adapter before scan — Pi 3B+ BT gets stuck without this
        try:
            subprocess.run(
                ["sudo", "hciconfig", "hci0", "reset"],
                capture_output=True, timeout=5
            )
        except Exception:
            pass
        ble_devices = self._scan_ble()
        classic_devices = self._scan_classic()

        # Deduplicate by MAC address
        all_macs = set()
        named_devices = []

        for mac, name in ble_devices:
            all_macs.add(mac.upper())
            if name and name != "(unknown)":
                named_devices.append(name)

        classic_count = 0
        for mac, name in classic_devices:
            mac_upper = mac.upper()
            if mac_upper not in all_macs:
                all_macs.add(mac_upper)
                classic_count += 1
            if name and name != "(unknown)" and name not in named_devices:
                named_devices.append(name)

        return {
            "ble_device_count": len(ble_devices),
            "classic_count": classic_count,
            "total_count": len(all_macs),
            "device_names": named_devices[:10],  # Cap at 10 names
        }

    def _scan_ble(self) -> List[tuple]:
        """BLE scan via hcitool lescan (brief, passive)."""
        devices = []
        try:
            # Use timeout to limit scan duration
            result = subprocess.run(
                ["sudo", "timeout", "5", "hcitool", "lescan", "--passive", "--duplicates"],
                capture_output=True, text=True, timeout=10
            )
            seen_macs = set()
            for line in result.stdout.splitlines():
                # Lines look like: "AA:BB:CC:DD:EE:FF DeviceName"
                match = re.match(r"([0-9A-Fa-f:]{17})\s+(.*)", line.strip())
                if match:
                    mac = match.group(1)
                    name = match.group(2).strip()
                    if mac.upper() not in seen_macs:
                        seen_macs.add(mac.upper())
                        devices.append((mac, name))
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.debug("BLE scan failed: %s", exc)
            # Try bluetoothctl as fallback
            devices = self._scan_ble_bluetoothctl()

        return devices

    def _scan_ble_bluetoothctl(self) -> List[tuple]:
        """Fallback BLE scan via bluetoothctl devices."""
        devices = []
        try:
            result = subprocess.run(
                ["bluetoothctl", "devices"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    # Lines: "Device AA:BB:CC:DD:EE:FF DeviceName"
                    match = re.match(r"Device\s+([0-9A-Fa-f:]{17})\s+(.*)", line.strip())
                    if match:
                        devices.append((match.group(1), match.group(2).strip()))
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.debug("bluetoothctl fallback failed: %s", exc)

        return devices

    def _scan_classic(self) -> List[tuple]:
        """Classic Bluetooth scan via hcitool scan."""
        devices = []
        try:
            result = subprocess.run(
                ["sudo", "timeout", "8", "hcitool", "scan"],
                capture_output=True, text=True, timeout=12
            )
            for line in result.stdout.splitlines():
                # Lines: "\tAA:BB:CC:DD:EE:FF\tDeviceName"
                match = re.match(r"\s+([0-9A-Fa-f:]{17})\s+(.*)", line)
                if match:
                    devices.append((match.group(1), match.group(2).strip()))
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.debug("Classic BT scan failed: %s", exc)

        return devices

    def _simulate(self) -> Dict[str, Any]:
        """Demo mode: return simulated Bluetooth scan data."""
        import random
        ble_count = random.randint(3, 15)
        classic_count = random.randint(0, 3)
        names = ["iPhone", "Galaxy Buds", "Tile Tracker", "AirPods Pro",
                 "Fitbit", "Echo Dot", "Smart Lock", "Pixel Watch"]
        sample_size = min(random.randint(2, 5), len(names))
        return {
            "ble_device_count": ble_count,
            "classic_count": classic_count,
            "total_count": ble_count + classic_count,
            "device_names": random.sample(names, sample_size),
        }
