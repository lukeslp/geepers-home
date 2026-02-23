"""System monitoring data source -- CPU, RAM, disk, uptime.

Reads from /proc and /sys on Linux. No external dependencies.
Lightweight enough for Pi 3B+ at 5-second intervals.
"""

import logging
import os
from typing import Any, Dict, Optional

from core.data_source import DataSource
from core.registry import register_source

logger = logging.getLogger(__name__)


@register_source("system")
class SystemSource(DataSource):
    """Publishes system metrics: CPU temp, RAM usage, disk usage, uptime."""

    def __init__(self, source_id: str, bus, config: Dict):
        config.setdefault("interval", 5.0)
        super().__init__(source_id, bus, config)

    def fetch(self) -> Optional[Dict[str, Any]]:
        data = {}

        # CPU temperature
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                data["cpu_temp"] = int(f.read().strip()) / 1000.0
        except (FileNotFoundError, ValueError):
            data["cpu_temp"] = 0.0

        # Memory from /proc/meminfo
        try:
            meminfo = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        meminfo[key] = int(val)
            total = meminfo.get("MemTotal", 1)
            available = meminfo.get("MemAvailable", 0)
            data["ram_total_mb"] = total / 1024
            data["ram_used_mb"] = (total - available) / 1024
            data["ram_percent"] = ((total - available) / total) * 100
        except Exception:
            data["ram_percent"] = 0.0
            data["ram_used_mb"] = 0.0
            data["ram_total_mb"] = 0.0

        # Disk usage
        try:
            st = os.statvfs("/")
            total = st.f_blocks * st.f_frsize
            free = st.f_bavail * st.f_frsize
            used = total - free
            data["disk_total_gb"] = total / (1024 ** 3)
            data["disk_used_gb"] = used / (1024 ** 3)
            data["disk_percent"] = (used / total) * 100 if total else 0
        except Exception:
            data["disk_percent"] = 0.0

        # Uptime
        try:
            with open("/proc/uptime") as f:
                seconds = float(f.read().split()[0])
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                data["uptime_hours"] = hours
                data["uptime_minutes"] = minutes
                data["uptime_str"] = f"{hours}h {minutes}m"
        except Exception:
            data["uptime_str"] = "?"

        # Load average
        try:
            with open("/proc/loadavg") as f:
                parts = f.read().split()
                data["load_1m"] = float(parts[0])
                data["load_5m"] = float(parts[1])
        except Exception:
            data["load_1m"] = 0.0

        return data
