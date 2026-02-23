"""Home Station -- extensible multi-page dashboard.

Loads card and source configuration from dashboard.yaml, instantiates
registered card types and data sources, and manages pages/navigation.

Preserves all UX from the original dashboard:
  - Detail overlay on card tap
  - Kiosk/ambient mode cycling
  - Alert borders at extreme thresholds
  - CSV logging
  - Demo mode toggle

New capabilities:
  - Multiple pages with prev/next navigation
  - Any card type (sensor, clock, system, custom)
  - Any data source (sensor, API, system, custom)
  - YAML configuration
  - Plugin discovery via registry decorators
"""

import tkinter as tk
import csv
import logging
import os
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional

from config import THEME, LOG_DIR, MAX_HISTORY

# Import core framework
from core import EventBus, PageManager
from core.registry import CARD_REGISTRY, SOURCE_REGISTRY

# Import card and source packages to trigger registration
import cards  # noqa: F401
import sources  # noqa: F401

logger = logging.getLogger(__name__)

# Layout constants
PAD = 8
GAP = 8
TOP_H = 36
BOT_H = 36


def load_config(path: str) -> Dict:
    """Load dashboard config from YAML file."""
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)
    except ImportError:
        # Fallback: parse YAML-like config manually if PyYAML not installed
        logger.warning("PyYAML not installed, using built-in config")
        return {}
    except FileNotFoundError:
        logger.warning("Config file not found: %s", path)
        return {}


def get_builtin_config() -> Dict:
    """Return the built-in default configuration (same as original dashboard)."""
    from config import DASHBOARD_CARDS
    pages = [{"name": "Environment", "cards": []}]
    source_ids = set()

    for card_cfg in DASHBOARD_CARDS:
        sensor_key = card_cfg["sensor"]
        source_id = f"sensor.{sensor_key}"
        pages[0]["cards"].append({
            "type": "sensor",
            "source_id": source_id,
            "sensor_key": sensor_key,
            "field": card_cfg["field"],
            "label": card_cfg["label"],
            "format": card_cfg.get("format", "{:.1f}"),
            "color": card_cfg["color"],
            "thresholds": card_cfg.get("thresholds", []),
        })
        source_ids.add((source_id, sensor_key))

    # Add system page
    pages.append({
        "name": "System",
        "cards": [
            {"type": "clock", "label": "Clock", "color": "#e0e0e0"},
            {"type": "system", "source_id": "system.stats", "label": "CPU",
             "metric": "cpu_temp", "color": "#ff9800"},
            {"type": "system", "source_id": "system.stats", "label": "Memory",
             "metric": "ram", "color": "#42a5f5"},
            {"type": "system", "source_id": "system.stats", "label": "Disk",
             "metric": "disk", "color": "#66bb6a"},
            {"type": "clock", "label": "Clock", "color": "#b0b0b0"},
            # Mirror temp on system page
            pages[0]["cards"][0].copy(),
        ],
    })

    sources_list = [
        {"id": sid, "type": "sensor", "sensor_key": skey}
        for sid, skey in source_ids
    ]
    sources_list.append({"id": "system.stats", "type": "system", "interval": 5})

    return {"pages": pages, "sources": sources_list}


class HomeStation:
    """Extensible multi-page dashboard."""

    def __init__(self, root, config_path: str = "dashboard.yaml"):
        self.root = root
        self.root.title("Home Station")
        self.root.configure(bg=THEME["bg"])

        # Fullscreen: overrideredirect bypasses the window manager entirely,
        # which is more reliable than -fullscreen under Xwayland/Wayfire.
        self.root.geometry("800x480+0+0")
        self.root.overrideredirect(True)
        self.root.bind("<Escape>", self._toggle_fullscreen)

        # State
        self.demo_mode = False
        self.logging_active = False
        self.log_file = None
        self.log_buffer = []
        self.log_flush_interval = 5000
        self.reading_count = 0
        self.kiosk_mode = False
        self._kiosk_idx = 0
        self._kiosk_overlay = None
        self._kiosk_interval = 8000

        # Core framework
        self.bus = EventBus(root)

        # Load config
        self._config = load_config(config_path)
        if not self._config.get("pages"):
            logger.info("Using built-in configuration")
            self._config = get_builtin_config()

        # Build UI
        self._build_top_bar()
        self._build_pages()
        self._build_bottom_bar()

        # Initialize and start data sources
        self._sources = {}
        self.root.after(100, self._start_sources)

    # ------------------------------------------------------------------
    # Source management
    # ------------------------------------------------------------------

    def _start_sources(self):
        """Create and start all configured data sources."""
        for src_cfg in self._config.get("sources", []):
            src_id = src_cfg.get("id", "")
            src_type = src_cfg.get("type", "")

            cls = SOURCE_REGISTRY.get(src_type)
            if not cls:
                logger.warning("Unknown source type: %s", src_type)
                continue

            if src_id in self._sources:
                continue  # already created

            try:
                config = dict(src_cfg)
                config["demo"] = self.demo_mode
                source = cls(src_id, self.bus, config)
                source.start()
                self._sources[src_id] = source
            except Exception as exc:
                logger.error("Failed to create source %s: %s", src_id, exc)

        # Subscribe to all sensor sources for counting/logging
        for src_id, source in self._sources.items():
            self.bus.subscribe(src_id, self._on_any_data)

        self._schedule_log_flush()
        self._update_status_bar()
        logger.info("Home Station: %d sources started", len(self._sources))

    def _on_any_data(self, payload):
        """Track reading counts and buffer for logging."""
        self.reading_count += 1
        if self.logging_active and isinstance(payload, dict):
            src = payload.get("_source", "?")
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            for field, value in payload.items():
                if not field.startswith("_"):
                    self.log_buffer.append([ts, src, field, value])

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_top_bar(self):
        bar = tk.Frame(self.root, bg=THEME["bg"], height=TOP_H)
        bar.pack(fill="x", padx=PAD)
        bar.pack_propagate(False)

        tk.Label(
            bar, text="HOME STATION", font=("Arial", 16, "bold"),
            bg=THEME["bg"], fg=THEME["text"],
        ).pack(side="left", padx=(4, 0))

        self._clock_lbl = tk.Label(
            bar, text="--:--", font=("Arial", 13),
            bg=THEME["bg"], fg=THEME["text_dim"],
        )
        self._clock_lbl.pack(side="left", padx=(16, 0))

        # Page indicator
        self._page_lbl = tk.Label(
            bar, text="", font=("Arial", 11),
            bg=THEME["bg"], fg=THEME["text_dim"],
        )
        self._page_lbl.pack(side="left", padx=(16, 0))

        # Buttons
        btn_kw = {
            "font": ("Arial", 11, "bold"), "relief": "flat",
            "width": 5, "cursor": "hand2",
        }

        self._exit_btn = tk.Button(
            bar, text="EXIT", bg="#444", fg="white",
            command=self.root.quit, **btn_kw,
        )
        self._exit_btn.pack(side="right", padx=2)

        self._log_btn = tk.Button(
            bar, text="LOG", bg=THEME["accent"], fg="white",
            command=self._toggle_logging, **btn_kw,
        )
        self._log_btn.pack(side="right", padx=2)

        self._kiosk_btn = tk.Button(
            bar, text="AUTO", bg=THEME["accent"], fg="white",
            command=self._toggle_kiosk, **btn_kw,
        )
        self._kiosk_btn.pack(side="right", padx=2)

        self._demo_btn = tk.Button(
            bar, text="DEMO", bg=THEME["accent"], fg="white",
            command=self._toggle_demo, **btn_kw,
        )
        self._demo_btn.pack(side="right", padx=2)

        # Page navigation (only shown if >1 page)
        self._prev_btn = tk.Button(
            bar, text="\u25c0", bg=THEME["accent"], fg="white",
            command=self._prev_page, font=("Arial", 11, "bold"),
            relief="flat", width=3, cursor="hand2",
        )
        self._next_btn = tk.Button(
            bar, text="\u25b6", bg=THEME["accent"], fg="white",
            command=self._next_page, font=("Arial", 11, "bold"),
            relief="flat", width=3, cursor="hand2",
        )

        self._update_clock()

    def _build_pages(self):
        """Create cards and organize into pages."""
        self._page_mgr = PageManager(self.root, cols=3, rows=2, gap=GAP)
        self._all_cards = []
        self._page_names = []

        for page_idx, page_cfg in enumerate(self._config.get("pages", [])):
            page_name = page_cfg.get("name", "Page")
            self._page_names.append(page_name)
            page_frame = self._page_mgr.create_page()

            for pos, card_cfg in enumerate(page_cfg.get("cards", [])):
                card_type = card_cfg.get("type", "sensor")
                cls = CARD_REGISTRY.get(card_type)
                if not cls:
                    logger.warning("Unknown card type: %s", card_type)
                    continue

                try:
                    card = cls(page_frame, self.bus, card_cfg)
                    self._all_cards.append(card)
                    self._page_mgr.place_card(card, page_idx, pos)

                    # Bind tap for cards that support it
                    if hasattr(card, "get_tappable_widgets"):
                        for widget in card.get_tappable_widgets():
                            widget.bind(
                                "<Button-1>",
                                lambda e, c=card: self._show_detail(c),
                            )
                except Exception as exc:
                    logger.error("Failed to create card %s: %s", card_type, exc)

        self._page_mgr.show_first_page()

        # Show/hide page navigation
        if self._page_mgr.page_count > 1:
            self._prev_btn.pack(side="right", padx=2)
            self._next_btn.pack(side="right", padx=2)

        self._update_page_indicator()

    def _build_bottom_bar(self):
        bar = tk.Frame(self.root, bg=THEME["bg"], height=BOT_H)
        bar.pack(fill="x", padx=PAD, pady=(0, 4))
        bar.pack_propagate(False)

        self._status_lbl = tk.Label(
            bar, text="Starting...", font=("Arial", 10),
            bg=THEME["bg"], fg=THEME["text_dim"],
        )
        self._status_lbl.pack(side="left", padx=4)

        self._count_lbl = tk.Label(
            bar, text="", font=("Arial", 10),
            bg=THEME["bg"], fg=THEME["text_dim"],
        )
        self._count_lbl.pack(side="right", padx=4)

    # ------------------------------------------------------------------
    # Page navigation
    # ------------------------------------------------------------------

    def _next_page(self):
        self._page_mgr.next_page()
        self._update_page_indicator()

    def _prev_page(self):
        self._page_mgr.prev_page()
        self._update_page_indicator()

    def _update_page_indicator(self):
        if self._page_mgr.page_count <= 1:
            self._page_lbl.config(text="")
            return
        idx = self._page_mgr.current_page
        name = self._page_names[idx] if idx < len(self._page_names) else ""
        dots = ""
        for i in range(self._page_mgr.page_count):
            dots += "\u25cf " if i == idx else "\u25cb "
        self._page_lbl.config(text=f"{name}  {dots.strip()}")

    # ------------------------------------------------------------------
    # Detail overlay (tap card to expand)
    # ------------------------------------------------------------------

    def _show_detail(self, card, kiosk=False):
        """Show full-screen detail overlay for a tapped card."""
        # Only sensor cards have detail views for now
        if not hasattr(card, "get_history"):
            return

        history = card.get_history()
        color = card.get_active_color()
        label = card.get_display_name()
        fmt = card.card_config.get("format", "{:.1f}")
        unit = getattr(card, "_unit", "")

        current = history[-1] if history else None

        # Overlay frame
        overlay = tk.Frame(self.root, bg=THEME["bg"])
        overlay.place(x=0, y=0, relwidth=1.0, relheight=1.0)

        if kiosk:
            self._kiosk_overlay = overlay

        def dismiss(e=None):
            if self.kiosk_mode:
                self._toggle_kiosk()
            overlay.destroy()
            self._kiosk_overlay = None

        overlay.bind("<Button-1>", dismiss)

        # Header
        hdr = tk.Frame(overlay, bg=THEME["bg"])
        hdr.pack(fill="x", padx=16, pady=(16, 0))
        hdr.bind("<Button-1>", dismiss)

        tk.Label(
            hdr, text=label, font=("Arial", 18, "bold"),
            bg=THEME["bg"], fg=THEME["text"],
        ).pack(side="left")

        tk.Label(
            hdr, text="tap to close", font=("Arial", 10),
            bg=THEME["bg"], fg=THEME["text_dim"],
        ).pack(side="right")

        # Big value
        if current is not None:
            try:
                val_text = fmt.format(current)
            except (ValueError, TypeError):
                val_text = str(current)
        else:
            val_text = "--"

        val_frame = tk.Frame(overlay, bg=THEME["bg"])
        val_frame.pack(fill="x", padx=16, pady=(8, 0))
        val_frame.bind("<Button-1>", dismiss)

        val_lbl = tk.Label(
            val_frame, text=val_text, font=("Arial", 64, "bold"),
            bg=THEME["bg"], fg=color,
        )
        val_lbl.pack(side="left")
        val_lbl.bind("<Button-1>", dismiss)

        unit_lbl = tk.Label(
            val_frame, text=f" {unit}", font=("Arial", 24),
            bg=THEME["bg"], fg=THEME["text_dim"],
        )
        unit_lbl.pack(side="left", anchor="s", pady=(0, 10))
        unit_lbl.bind("<Button-1>", dismiss)

        # Graph
        graph = tk.Canvas(
            overlay, bg=THEME["graph_bg"], height=200, highlightthickness=0,
        )
        graph.pack(fill="x", padx=16, pady=(12, 8))
        graph.bind("<Button-1>", dismiss)

        overlay.update_idletasks()
        self._draw_detail_graph(graph, history, color, unit, fmt)

        # Stats
        stats = tk.Frame(overlay, bg=THEME["bg"])
        stats.pack(fill="x", padx=16, pady=(0, 8))
        stats.bind("<Button-1>", dismiss)

        if len(history) >= 2:
            mn, mx = min(history), max(history)
            avg = sum(history) / len(history)
            for stat_label, stat_val in [("MIN", mn), ("AVG", avg), ("MAX", mx)]:
                sf = tk.Frame(stats, bg=THEME["bg"])
                sf.pack(side="left", expand=True)
                sf.bind("<Button-1>", dismiss)
                s_val = tk.Label(
                    sf, text=fmt.format(stat_val), font=("Arial", 20, "bold"),
                    bg=THEME["bg"], fg=THEME["text"],
                )
                s_val.pack()
                s_val.bind("<Button-1>", dismiss)
                s_lbl = tk.Label(
                    sf, text=stat_label, font=("Arial", 9),
                    bg=THEME["bg"], fg=THEME["text_dim"],
                )
                s_lbl.pack()
                s_lbl.bind("<Button-1>", dismiss)

        count_lbl = tk.Label(
            overlay, text=f"{len(history)} readings", font=("Arial", 10),
            bg=THEME["bg"], fg=THEME["text_dim"],
        )
        count_lbl.pack(pady=(4, 0))
        count_lbl.bind("<Button-1>", dismiss)

    def _draw_detail_graph(self, canvas, data, color, unit, fmt):
        """Draw expanded graph with grid and labels."""
        if len(data) < 2:
            canvas.create_text(
                canvas.winfo_width() // 2, canvas.winfo_height() // 2,
                text="Collecting data...", fill=THEME["text_dim"], font=("Arial", 12),
            )
            return

        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 40 or h < 40:
            return

        left, right, top_m, bot = 52, 12, 12, 24
        pw, ph = w - left - right, h - top_m - bot
        d_min, d_max = min(data), max(data)
        d_range = d_max - d_min if d_max != d_min else 1

        # Grid lines
        for i in range(4):
            y = top_m + (i / 3) * ph
            val = d_max - (i / 3) * d_range
            canvas.create_line(left, y, w - right, y, fill="#333", dash=(2, 4))
            try:
                label = fmt.format(val)
            except (ValueError, TypeError):
                label = f"{val:.1f}"
            canvas.create_text(
                left - 6, y, text=label, anchor="e",
                fill=THEME["text_dim"], font=("Arial", 8),
            )

        n = len(data)
        points = []
        for i, val in enumerate(data):
            x = left + (i / (n - 1)) * pw
            y = top_m + (1.0 - (val - d_min) / d_range) * ph
            points.append((x, y))

        # Fill
        fill_pts = list(points) + [(points[-1][0], top_m + ph), (points[0][0], top_m + ph)]
        flat = [coord for pt in fill_pts for coord in pt]
        try:
            r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            fill_color = f"#{r // 4:02x}{g // 4:02x}{b // 4:02x}"
        except (ValueError, IndexError):
            fill_color = "#111111"
        canvas.create_polygon(flat, fill=fill_color, outline="")

        # Line
        for i in range(len(points) - 1):
            canvas.create_line(
                points[i][0], points[i][1], points[i + 1][0], points[i + 1][1],
                fill=color, width=2,
            )

        # Current dot
        lx, ly = points[-1]
        canvas.create_oval(lx - 4, ly - 4, lx + 4, ly + 4, fill=color, outline="")

    # ------------------------------------------------------------------
    # Clock + status
    # ------------------------------------------------------------------

    def _update_clock(self):
        self._clock_lbl.config(text=datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000, self._update_clock)

    def _update_status_bar(self):
        live = sum(
            1 for s in self._sources.values()
            if hasattr(s, '_sensor') and s._sensor and not s._sensor.simulated
        )
        total = len(self._sources)
        mode = "DEMO" if self.demo_mode else "LIVE"
        self._status_lbl.config(text=f"{live}/{total} sources  \u2502  {mode}")
        self._count_lbl.config(text=f"Readings: {self.reading_count}")
        self.root.after(2000, self._update_status_bar)

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def _toggle_demo(self):
        self.demo_mode = not self.demo_mode
        if self.demo_mode:
            self._demo_btn.config(bg=THEME["warning"], fg="#000")
        else:
            self._demo_btn.config(bg=THEME["accent"], fg="white")
        # Update all sensor sources
        for source in self._sources.values():
            if hasattr(source, "set_demo"):
                source.set_demo(self.demo_mode)

    def _toggle_kiosk(self):
        self.kiosk_mode = not self.kiosk_mode
        if self.kiosk_mode:
            self._kiosk_btn.config(bg=THEME["warning"], fg="#000")
            self._kiosk_idx = 0
            self._kiosk_cycle()
        else:
            self._kiosk_btn.config(bg=THEME["accent"], fg="white")
            if self._kiosk_overlay:
                self._kiosk_overlay.destroy()
                self._kiosk_overlay = None

    def _kiosk_cycle(self):
        if not self.kiosk_mode:
            return
        # Only cycle sensor cards
        sensor_cards = [c for c in self._all_cards if hasattr(c, "get_history")]
        if not sensor_cards:
            return

        if self._kiosk_overlay:
            self._kiosk_overlay.destroy()
            self._kiosk_overlay = None

        card = sensor_cards[self._kiosk_idx % len(sensor_cards)]
        self._kiosk_idx = (self._kiosk_idx + 1) % len(sensor_cards)
        self._show_detail(card, kiosk=True)
        self.root.after(self._kiosk_interval, self._kiosk_cycle)

    def _toggle_logging(self):
        if not self.logging_active:
            os.makedirs(LOG_DIR, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file = os.path.join(LOG_DIR, f"sensor_log_{ts}.csv")
            with open(self.log_file, "w", newline="") as f:
                csv.writer(f).writerow(["timestamp", "source", "field", "value"])
            self.logging_active = True
            self._log_btn.config(bg=THEME["error"], text="STOP")
        else:
            self._flush_log_buffer()
            self.logging_active = False
            self._log_btn.config(bg=THEME["accent"], text="LOG")

    def _flush_log_buffer(self):
        if not self.log_file or not self.log_buffer:
            return
        try:
            with open(self.log_file, "a", newline="") as f:
                csv.writer(f).writerows(self.log_buffer)
            self.log_buffer.clear()
        except Exception as exc:
            logger.error("Log flush failed: %s", exc)

    def _schedule_log_flush(self):
        if self.logging_active:
            self._flush_log_buffer()
        self.root.after(self.log_flush_interval, self._schedule_log_flush)

    def _toggle_fullscreen(self, event=None):
        if self.root.overrideredirect():
            self.root.overrideredirect(False)
            self.root.geometry("600x400")
        else:
            self.root.overrideredirect(True)
            self.root.geometry("800x480+0+0")

    def cleanup(self):
        """Release all resources."""
        self._flush_log_buffer()
        for source in self._sources.values():
            source.close()
