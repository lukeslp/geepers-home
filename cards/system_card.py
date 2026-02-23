"""System monitoring card -- CPU temperature, RAM, disk usage.

Subscribes to a SystemSource and displays key system metrics
in a compact card format. Shows the most critical metric large
(CPU temp) with RAM/disk as secondary stats.
"""

import tkinter as tk
from typing import Dict

from core.base_card import BaseCard
from core.registry import register_card
from config import THEME


@register_card("system")
class SystemCard(BaseCard):
    """System health overview: CPU temp, RAM, disk, uptime."""

    def __init__(self, parent, bus, config: Dict):
        self._metric = config.get("metric", "cpu_temp")
        config.setdefault("bg", THEME["card_bg"])
        config.setdefault("label", "System")
        super().__init__(parent, bus, config)

    def setup_ui(self):
        bg = self.card_config.get("bg", THEME["card_bg"])
        color = self.card_config.get("color", "#ff9800")

        # Top label
        top = tk.Frame(self, bg=bg)
        top.pack(fill="x", padx=12, pady=(10, 0))

        self._icon_lbl = tk.Label(
            top, text="\u2699", font=("Arial", 10), bg=bg, fg=THEME["text_dim"],
        )
        self._icon_lbl.pack(side="left")

        tk.Label(
            top,
            text=self.card_config.get("label", "System"),
            font=("Arial", 11),
            bg=bg,
            fg=THEME["text_dim"],
        ).pack(side="left", padx=(4, 0))

        # Primary metric (big)
        mid = tk.Frame(self, bg=bg)
        mid.pack(fill="both", expand=True, padx=12)

        self._value_lbl = tk.Label(
            mid, text="--", font=("Arial", 32, "bold"), bg=bg, fg=color,
        )
        self._value_lbl.pack(anchor="center", pady=(4, 0))

        self._sub_lbl = tk.Label(
            mid, text="", font=("Arial", 10), bg=bg, fg=THEME["text_dim"],
        )
        self._sub_lbl.pack(anchor="center")

        # Secondary stats row
        self._stats_frame = tk.Frame(self, bg=bg)
        self._stats_frame.pack(fill="x", padx=12, pady=(0, 10))

        self._stat1 = tk.Label(
            self._stats_frame, text="", font=("Arial", 9), bg=bg, fg=THEME["text_dim"],
        )
        self._stat1.pack(side="left")

        self._stat2 = tk.Label(
            self._stats_frame, text="", font=("Arial", 9), bg=bg, fg=THEME["text_dim"],
        )
        self._stat2.pack(side="right")

    def on_data(self, payload: Dict):
        metric = self._metric

        if metric == "cpu_temp":
            temp = payload.get("cpu_temp", 0)
            color = self._temp_color(temp)
            self._value_lbl.config(text=f"{temp:.1f}", fg=color)
            self._sub_lbl.config(text="\u00b0C CPU")
            ram = payload.get("ram_percent", 0)
            self._stat1.config(text=f"RAM {ram:.0f}%")
            disk = payload.get("disk_percent", 0)
            self._stat2.config(text=f"Disk {disk:.0f}%")

        elif metric == "ram":
            ram = payload.get("ram_percent", 0)
            used = payload.get("ram_used_mb", 0)
            total = payload.get("ram_total_mb", 0)
            color = "#00d084" if ram < 70 else "#ffa726" if ram < 85 else "#ff5252"
            self._value_lbl.config(text=f"{ram:.0f}%", fg=color)
            self._sub_lbl.config(text=f"{used:.0f}/{total:.0f} MB")
            temp = payload.get("cpu_temp", 0)
            self._stat1.config(text=f"CPU {temp:.0f}\u00b0C")
            up = payload.get("uptime_str", "?")
            self._stat2.config(text=f"Up {up}")

        elif metric == "disk":
            disk = payload.get("disk_percent", 0)
            used = payload.get("disk_used_gb", 0)
            total = payload.get("disk_total_gb", 0)
            color = "#00d084" if disk < 70 else "#ffa726" if disk < 85 else "#ff5252"
            self._value_lbl.config(text=f"{disk:.0f}%", fg=color)
            self._sub_lbl.config(text=f"{used:.1f}/{total:.1f} GB")
            load = payload.get("load_1m", 0)
            self._stat1.config(text=f"Load {load:.2f}")
            up = payload.get("uptime_str", "?")
            self._stat2.config(text=f"Up {up}")

    @staticmethod
    def _temp_color(temp):
        if temp < 50:
            return "#00d084"
        elif temp < 65:
            return "#ffa726"
        elif temp < 75:
            return "#ff9100"
        return "#ff5252"
