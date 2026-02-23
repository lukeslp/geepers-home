"""Vision description card -- shows LLM scene analysis.

Subscribes to camera.vision and displays the latest scene description
returned by the VPS vision API. Updates on the configured vision
source interval (default 60s).
"""

import tkinter as tk
import logging
from typing import Dict

from core.base_card import BaseCard
from core.registry import register_card
from config import THEME

logger = logging.getLogger(__name__)


@register_card("vision")
class VisionCard(BaseCard):
    """Displays LLM scene description from camera feed."""

    def __init__(self, parent, bus, config: Dict):
        self._label_text = config.get("label", "Scene")
        self._color = config.get("color", "#ab47bc")
        config.setdefault("bg", THEME["card_bg"])
        super().__init__(parent, bus, config)

    def setup_ui(self):
        bg = self.card_config.get("bg", THEME["card_bg"])

        # Top: icon + label + timestamp
        top = tk.Frame(self, bg=bg)
        top.pack(fill="x", padx=8, pady=(6, 0))

        tk.Label(
            top, text="\u25c9", font=("Arial", 10), bg=bg, fg=self._color,
        ).pack(side="left")

        tk.Label(
            top, text=self._label_text, font=("Arial", 11),
            bg=bg, fg=THEME["text_dim"],
        ).pack(side="left", padx=(4, 0))

        self._time_lbl = tk.Label(
            top, text="", font=("Arial", 9), bg=bg, fg=THEME["text_dim"],
        )
        self._time_lbl.pack(side="right")

        # Description text area
        self._desc_lbl = tk.Label(
            self, text="Waiting for analysis...",
            font=("Arial", 10), bg=bg, fg=THEME["text"],
            wraplength=220, justify="left", anchor="nw",
        )
        self._desc_lbl.pack(fill="both", expand=True, padx=8, pady=(4, 8))

    def on_data(self, payload: Dict):
        desc = payload.get("description", "")
        timestamp = payload.get("timestamp", "")

        if desc:
            # Truncate long descriptions for card display
            display = desc[:120] + "..." if len(desc) > 120 else desc
            self._desc_lbl.config(text=display)

        if timestamp:
            self._time_lbl.config(text=timestamp)

    def get_tappable_widgets(self):
        return [self, self._desc_lbl]
