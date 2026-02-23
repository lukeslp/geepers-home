"""Clock card -- displays current time and date.

A simple card that doesn't need a DataSource. It updates itself
every second using root.after(). Shows time in large digits and
date below.
"""

import tkinter as tk
from datetime import datetime
from typing import Dict

from core.base_card import BaseCard
from core.registry import register_card
from config import THEME


@register_card("clock")
class ClockCard(BaseCard):
    """Large clock display with date."""

    def __init__(self, parent, bus, config: Dict):
        config.setdefault("bg", THEME["card_bg"])
        config.setdefault("label", "Clock")
        super().__init__(parent, bus, config)
        self._tick()

    def setup_ui(self):
        bg = self.card_config.get("bg", THEME["card_bg"])
        color = self.card_config.get("color", "#e0e0e0")

        self._time_lbl = tk.Label(
            self,
            text="--:--",
            font=("Arial", 40, "bold"),
            bg=bg,
            fg=color,
        )
        self._time_lbl.pack(expand=True, anchor="center", pady=(8, 0))

        self._date_lbl = tk.Label(
            self,
            text="",
            font=("Arial", 11),
            bg=bg,
            fg=THEME["text_dim"],
        )
        self._date_lbl.pack(anchor="center", pady=(0, 12))

    def on_data(self, payload: Dict):
        # Clock doesn't use external data
        pass

    def _tick(self):
        now = datetime.now()
        self._time_lbl.config(text=now.strftime("%H:%M"))
        self._date_lbl.config(text=now.strftime("%A, %B %d"))
        self.after(1000, self._tick)
