"""Sensor metric card -- displays a single sensor reading with sparkline.

This is a refactored version of the original dashboard card, now using
the BaseCard framework. Shows: status dot, label, big value with
threshold coloring, unit, sparkline graph, and min/max stats.
"""

import tkinter as tk
import logging
from collections import deque
from typing import Any, Dict, Optional

from core.base_card import BaseCard
from core.registry import register_card
from config import THEME, SENSORS

logger = logging.getLogger(__name__)


@register_card("sensor")
class SensorCard(BaseCard):
    """Single sensor metric with sparkline and threshold coloring."""

    def __init__(self, parent, bus, config: Dict):
        # Pre-extract config before setup_ui
        self._field_key = config.get("field", "")
        self._color = config.get("color", "#e0e0e0")
        self._format = config.get("format", "{:.1f}")
        self._thresholds = config.get("thresholds", [])
        self._label = config.get("label", "Sensor")

        # Get unit from sensor config
        sensor_key = config.get("sensor_key", "")
        sensor_cfg = SENSORS.get(sensor_key, {})
        field_info = sensor_cfg.get("fields", {}).get(self._field_key, {})
        self._unit = field_info.get("unit", config.get("unit", ""))

        # History for sparkline
        self._data_history = deque(maxlen=config.get("history_len", 200))

        config.setdefault("bg", THEME["card_bg"])
        super().__init__(parent, bus, config)

    def setup_ui(self):
        bg = self.card_config.get("bg", THEME["card_bg"])

        # Top: status dot + label
        top = tk.Frame(self, bg=bg)
        top.pack(fill="x", padx=12, pady=(10, 0))

        self._status_dot = tk.Label(
            top, text="\u25cb", font=("Arial", 10), bg=bg, fg=THEME["text_dim"],
        )
        self._status_dot.pack(side="left")

        tk.Label(
            top, text=self._label, font=("Arial", 11), bg=bg, fg=THEME["text_dim"],
        ).pack(side="left", padx=(4, 0))

        # Center: big value + unit
        mid = tk.Frame(self, bg=bg)
        mid.pack(fill="both", expand=True, padx=12)

        self._value_lbl = tk.Label(
            mid, text="--", font=("Arial", 36, "bold"), bg=bg, fg=self._color,
        )
        self._value_lbl.pack(anchor="center", pady=(4, 0))

        self._unit_lbl = tk.Label(
            mid, text=self._unit, font=("Arial", 11), bg=bg, fg=THEME["text_dim"],
        )
        self._unit_lbl.pack(anchor="center")

        # Sparkline
        self._spark = tk.Canvas(
            self, bg=THEME["graph_bg"], height=44, highlightthickness=0,
        )
        self._spark.pack(fill="x", padx=12, pady=(0, 2))

        # Stats (min/max)
        self._stats_lbl = tk.Label(
            self, text="", font=("Arial", 8), bg=bg, fg=THEME["text_dim"],
        )
        self._stats_lbl.pack(padx=12, pady=(0, 8), anchor="w")

        # Make all widgets tappable
        self._tappable_widgets = [
            self, mid, top, self._value_lbl, self._unit_lbl,
            self._spark, self._stats_lbl, self._status_dot,
        ]

    def on_data(self, payload: Dict):
        value = payload.get(self._field_key)
        if value is None:
            return

        # Track history
        if isinstance(value, (int, float)):
            self._data_history.append(value)

        # Format value text
        try:
            text = self._format.format(value)
        except (ValueError, TypeError):
            text = str(value)

        # Threshold coloring
        active_color = self._color
        threshold_idx = 0
        if self._thresholds and isinstance(value, (int, float)):
            for i, (tval, tcolor) in enumerate(self._thresholds):
                if value <= tval:
                    active_color = tcolor
                    threshold_idx = i
                    break

        self._value_lbl.config(text=text, fg=active_color)

        # Alert border at extremes
        n = len(self._thresholds)
        if n >= 3 and (threshold_idx == 0 or threshold_idx >= n - 1):
            self.config(highlightbackground=active_color, highlightthickness=2)
        else:
            self.config(highlightbackground=THEME["accent"], highlightthickness=1)

        # Status dot
        is_sim = payload.get("_simulated", True)
        if is_sim:
            self._status_dot.config(text="\u25c9", fg=THEME["warning"])
        else:
            self._status_dot.config(text="\u25cf", fg=THEME["success"])

        # Sparkline
        self._draw_sparkline(list(self._data_history), active_color)

        # Min/max stats
        data = list(self._data_history)
        if len(data) >= 2:
            mn, mx = min(data), max(data)
            self._stats_lbl.config(
                text=f"min {mn:.1f}{self._unit}  max {mx:.1f}{self._unit}"
            )

    def _draw_sparkline(self, data, color):
        canvas = self._spark
        canvas.delete("all")
        if len(data) < 2:
            return

        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 20 or h < 10:
            return

        px, py = 4, 4
        pw, ph = w - 2 * px, h - 2 * py
        d_min, d_max = min(data), max(data)
        d_range = d_max - d_min if d_max != d_min else 1
        n = len(data)

        points = []
        for i, val in enumerate(data):
            x = px + (i / (n - 1)) * pw
            y = py + (1.0 - (val - d_min) / d_range) * ph
            points.append((x, y))

        # Fill under line
        fill_pts = list(points) + [(points[-1][0], h - py), (points[0][0], h - py)]
        flat = [coord for pt in fill_pts for coord in pt]
        try:
            r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            fill_color = f"#{r // 5:02x}{g // 5:02x}{b // 5:02x}"
        except (ValueError, IndexError):
            fill_color = "#111111"
        canvas.create_polygon(flat, fill=fill_color, outline="")

        # Line trace
        for i in range(len(points) - 1):
            canvas.create_line(
                points[i][0], points[i][1], points[i + 1][0], points[i + 1][1],
                fill=color, width=2,
            )

        # Current dot
        lx, ly = points[-1]
        canvas.create_oval(lx - 3, ly - 3, lx + 3, ly + 3, fill=color, outline="")

    def get_history(self):
        """Return data history for detail overlay."""
        return list(self._data_history)

    def get_active_color(self):
        """Get current threshold color based on latest value."""
        if not self._data_history:
            return self._color
        value = self._data_history[-1]
        if self._thresholds and isinstance(value, (int, float)):
            for tval, tcolor in self._thresholds:
                if value <= tval:
                    return tcolor
        return self._color

    def get_tappable_widgets(self):
        """Return list of widgets that should trigger tap events."""
        return self._tappable_widgets
