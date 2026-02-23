"""Camera preview card -- live webcam thumbnail with motion indicator.

Subscribes to camera.feed and renders the latest frame as a thumbnail.
PIL Image arrives from the EventBus (main thread), gets converted to
ImageTk.PhotoImage for display. Previous photo ref is released each
update to avoid memory accumulation.
"""

import tkinter as tk
import logging
from typing import Dict

from core.base_card import BaseCard
from core.registry import register_card
from config import THEME

logger = logging.getLogger(__name__)

try:
    from PIL import ImageTk, Image
    HAS_IMAGETK = True
except ImportError:
    HAS_IMAGETK = False


@register_card("camera")
class CameraCard(BaseCard):
    """Live camera preview with motion indicator."""

    def __init__(self, parent, bus, config: Dict):
        self._label_text = config.get("label", "Camera")
        self._color = config.get("color", "#42a5f5")
        config.setdefault("bg", THEME["card_bg"])
        self._photo_ref = None  # prevent GC of current PhotoImage
        super().__init__(parent, bus, config)

    def setup_ui(self):
        bg = self.card_config.get("bg", THEME["card_bg"])

        # Top row: status dot + label + motion text
        top = tk.Frame(self, bg=bg)
        top.pack(fill="x", padx=8, pady=(6, 0))

        self._status_dot = tk.Label(
            top, text="\u25cb", font=("Arial", 10), bg=bg, fg=THEME["text_dim"],
        )
        self._status_dot.pack(side="left")

        tk.Label(
            top, text=self._label_text, font=("Arial", 11),
            bg=bg, fg=THEME["text_dim"],
        ).pack(side="left", padx=(4, 0))

        self._motion_lbl = tk.Label(
            top, text="", font=("Arial", 9), bg=bg, fg=THEME["text_dim"],
        )
        self._motion_lbl.pack(side="right")

        # Center: camera preview image
        self._preview_lbl = tk.Label(
            self, bg=THEME["graph_bg"], text="No camera",
            fg=THEME["text_dim"], font=("Arial", 10),
        )
        self._preview_lbl.pack(fill="both", expand=True, padx=8, pady=(4, 8))

    def on_data(self, payload: Dict):
        if not HAS_IMAGETK:
            return

        frame = payload.get("frame")
        if frame is None:
            return

        motion = payload.get("motion", False)
        motion_pct = payload.get("motion_pct", 0.0)

        # Resize frame to fit the label widget
        try:
            w = self._preview_lbl.winfo_width()
            h = self._preview_lbl.winfo_height()
            if w < 20 or h < 20:
                w, h = 230, 130

            thumb = frame.copy()
            thumb.thumbnail((w, h), Image.LANCZOS)

            self._photo_ref = ImageTk.PhotoImage(thumb)
            self._preview_lbl.config(image=self._photo_ref, text="")
        except Exception as exc:
            logger.error("Camera card render error: %s", exc)
            return

        # Motion indicator
        if motion:
            self._status_dot.config(text="\u25cf", fg="#ff5252")
            self._motion_lbl.config(
                text=f"Motion {motion_pct:.0f}%", fg="#ff5252",
            )
        else:
            self._status_dot.config(text="\u25cf", fg=THEME["success"])
            self._motion_lbl.config(text="", fg=THEME["text_dim"])

    def get_tappable_widgets(self):
        return [self, self._preview_lbl, self._status_dot]
