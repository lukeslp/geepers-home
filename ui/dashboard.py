"""Environment Dashboard — single-screen view for Waveshare HAT sensors.

Replaces the tab-based Sensor Playground with a 3x2 card grid optimized
for the 800x480 touchscreen. Each card shows one sensor metric with a
real-time sparkline graph.

Layout (800 x 480):
  +--------------------------------------------------+
  |  HOME STATION     20:15        [DEMO] [LOG] [X]  |  36px
  +--------------------------------------------------+
  | +--------+ +--------+ +--------+                  |
  | |  22.4  | |   58   | |  1013  |                  |
  | |   °C   | |    %   | |   hPa  |                  | ~192px
  | |  Temp  | | Humid  | |  Press |                  |
  | | ~~~~~~ | | ~~~~~~ | | ~~~~~~ |                  |
  | +--------+ +--------+ +--------+                  |
  | +--------+ +--------+ +--------+                  |
  | |  342   | |  2.1   | |  Good  |                  |
  | |  lux   | |        | |        |                  | ~192px
  | | Light  | | UV Idx | | Air Q  |                  |
  | | ~~~~~~ | | ~~~~~~ | | ~~~~~~ |                  |
  | +--------+ +--------+ +--------+                  |
  +--------------------------------------------------+
  |  5 live  •  142 readings                          |  36px
  +--------------------------------------------------+
"""

import tkinter as tk
from collections import deque
from datetime import datetime
import csv
import os
import logging
import threading

from config import SENSORS, THEME, MAX_HISTORY, LOG_DIR, DASHBOARD_CARDS
from sensors import SENSOR_CLASSES

logger = logging.getLogger(__name__)

# Layout constants
COLS = 3
ROWS = 2
PAD = 8
GAP = 8
TOP_H = 36
BOT_H = 36


class EnvironmentDashboard:
    """Single-screen dashboard showing 6 sensor cards in a 3x2 grid."""

    def __init__(self, root):
        self.root = root
        self.root.title("Home Station")
        self.root.configure(bg=THEME["bg"])
        self.root.attributes("-fullscreen", True)
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
        self._kiosk_interval = 8000  # ms between card switches

        # Initialize sensors
        self._init_sensors()

        # Build UI
        logger.info("Building dashboard UI...")
        self._build_top_bar()
        self._build_card_grid()
        self._build_bottom_bar()
        logger.info("Dashboard UI built.")

        # Defer polling until mainloop runs
        self.root.after(100, self._start_polling)

    # ------------------------------------------------------------------
    # Sensor initialization
    # ------------------------------------------------------------------

    def _init_sensors(self):
        """Initialize only the sensors needed for the dashboard."""
        logger.info("Initializing dashboard sensors...")
        self.sensors = {}
        self.histories = {}

        # Collect unique sensor keys from dashboard cards
        needed = set()
        for card in DASHBOARD_CARDS:
            needed.add(card["sensor"])

        for key in needed:
            cfg = SENSORS.get(key)
            cls = SENSOR_CLASSES.get(key)
            if cfg and cls:
                logger.debug("  init %s ...", key)
                self.sensors[key] = cls(cfg["pin"], cfg)
                self.histories[key] = {
                    field: deque(maxlen=MAX_HISTORY)
                    for field in cfg["fields"]
                }

        logger.info(
            "Dashboard sensors ready (%d loaded).", len(self.sensors)
        )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_top_bar(self):
        """Status bar with title, clock, and control buttons."""
        bar = tk.Frame(self.root, bg=THEME["bg"], height=TOP_H)
        bar.pack(fill="x", padx=PAD)
        bar.pack_propagate(False)

        tk.Label(
            bar,
            text="HOME STATION",
            font=("Arial", 16, "bold"),
            bg=THEME["bg"],
            fg=THEME["text"],
        ).pack(side="left", padx=(4, 0))

        self._clock_lbl = tk.Label(
            bar,
            text="--:--",
            font=("Arial", 13),
            bg=THEME["bg"],
            fg=THEME["text_dim"],
        )
        self._clock_lbl.pack(side="left", padx=(16, 0))

        # Control buttons (right-aligned)
        btn_kw = {
            "font": ("Arial", 11, "bold"),
            "relief": "flat",
            "width": 5,
            "cursor": "hand2",
        }

        self._exit_btn = tk.Button(
            bar,
            text="EXIT",
            bg="#444",
            fg="white",
            command=self.root.quit,
            **btn_kw,
        )
        self._exit_btn.pack(side="right", padx=2)

        self._log_btn = tk.Button(
            bar,
            text="LOG",
            bg=THEME["accent"],
            fg="white",
            command=self._toggle_logging,
            **btn_kw,
        )
        self._log_btn.pack(side="right", padx=2)

        self._kiosk_btn = tk.Button(
            bar,
            text="AUTO",
            bg=THEME["accent"],
            fg="white",
            command=self._toggle_kiosk,
            **btn_kw,
        )
        self._kiosk_btn.pack(side="right", padx=2)

        self._demo_btn = tk.Button(
            bar,
            text="DEMO",
            bg=THEME["accent"],
            fg="white",
            command=self._toggle_demo,
            **btn_kw,
        )
        self._demo_btn.pack(side="right", padx=2)

        self._update_clock()

    def _build_card_grid(self):
        """Build 3x2 grid of sensor cards."""
        self._grid = tk.Frame(self.root, bg=THEME["bg"])
        self._grid.pack(fill="both", expand=True, padx=PAD, pady=(4, 4))

        for col in range(COLS):
            self._grid.columnconfigure(col, weight=1, uniform="card")
        for row in range(ROWS):
            self._grid.rowconfigure(row, weight=1, uniform="card")

        self._cards = []
        for i, card_cfg in enumerate(DASHBOARD_CARDS[: COLS * ROWS]):
            row = i // COLS
            col = i % COLS
            card = self._build_card(card_cfg, row, col)
            self._cards.append(card)

    def _build_card(self, card_cfg, row, col):
        """Build a single sensor card widget."""
        sensor_key = card_cfg["sensor"]
        field_key = card_cfg["field"]
        color = card_cfg["color"]
        label = card_cfg["label"]
        fmt = card_cfg.get("format", "{:.1f}")

        # Pull unit from sensor config
        sensor_cfg = SENSORS.get(sensor_key, {})
        field_info = sensor_cfg.get("fields", {}).get(field_key, {})
        unit = field_info.get("unit", "")

        # Card frame
        card = tk.Frame(
            self._grid,
            bg=THEME["card_bg"],
            highlightbackground=THEME["accent"],
            highlightthickness=1,
        )
        card.grid(
            row=row,
            column=col,
            padx=GAP // 2,
            pady=GAP // 2,
            sticky="nsew",
        )

        # Store metadata on the widget for updates
        card._sensor_key = sensor_key
        card._field_key = field_key
        card._color = color
        card._format = fmt
        card._unit = unit
        card._thresholds = card_cfg.get("thresholds", [])

        # --- Top row: status dot + label ---
        top = tk.Frame(card, bg=THEME["card_bg"])
        top.pack(fill="x", padx=12, pady=(10, 0))

        card._status_dot = tk.Label(
            top,
            text="\u25cb",
            font=("Arial", 10),
            bg=THEME["card_bg"],
            fg=THEME["text_dim"],
        )
        card._status_dot.pack(side="left")

        tk.Label(
            top,
            text=label,
            font=("Arial", 11),
            bg=THEME["card_bg"],
            fg=THEME["text_dim"],
        ).pack(side="left", padx=(4, 0))

        # --- Center: big value + unit ---
        mid = tk.Frame(card, bg=THEME["card_bg"])
        mid.pack(fill="both", expand=True, padx=12)

        card._value_lbl = tk.Label(
            mid,
            text="--",
            font=("Arial", 36, "bold"),
            bg=THEME["card_bg"],
            fg=color,
        )
        card._value_lbl.pack(anchor="center", pady=(4, 0))

        card._unit_lbl = tk.Label(
            mid,
            text=unit,
            font=("Arial", 11),
            bg=THEME["card_bg"],
            fg=THEME["text_dim"],
        )
        card._unit_lbl.pack(anchor="center")

        # --- Sparkline canvas ---
        card._spark = tk.Canvas(
            card,
            bg=THEME["graph_bg"],
            height=44,
            highlightthickness=0,
        )
        card._spark.pack(fill="x", padx=12, pady=(0, 2))

        # --- Stats (min / max) ---
        card._stats_lbl = tk.Label(
            card,
            text="",
            font=("Arial", 8),
            bg=THEME["card_bg"],
            fg=THEME["text_dim"],
        )
        card._stats_lbl.pack(padx=12, pady=(0, 8), anchor="w")

        # Tap card for detail overlay
        card._label_text = label
        for widget in (card, mid, top, card._value_lbl, card._unit_lbl,
                       card._spark, card._stats_lbl, card._status_dot):
            widget.bind("<Button-1>", lambda e, c=card: self._show_detail(c))

        return card

    def _build_bottom_bar(self):
        """Bottom bar: sensor count, reading count."""
        bar = tk.Frame(self.root, bg=THEME["bg"], height=BOT_H)
        bar.pack(fill="x", padx=PAD, pady=(0, 4))
        bar.pack_propagate(False)

        self._status_lbl = tk.Label(
            bar,
            text="Starting...",
            font=("Arial", 10),
            bg=THEME["bg"],
            fg=THEME["text_dim"],
        )
        self._status_lbl.pack(side="left", padx=4)

        self._count_lbl = tk.Label(
            bar,
            text="",
            font=("Arial", 10),
            bg=THEME["bg"],
            fg=THEME["text_dim"],
        )
        self._count_lbl.pack(side="right", padx=4)

    # ------------------------------------------------------------------
    # Sensor polling (threaded — same pattern as app.py)
    # ------------------------------------------------------------------

    def _start_polling(self):
        """Stagger sensor polling start to avoid I2C bus contention."""
        needed = []
        seen = set()
        for card in DASHBOARD_CARDS:
            if card["sensor"] not in seen:
                needed.append(card["sensor"])
                seen.add(card["sensor"])

        for i, key in enumerate(needed):
            cfg = SENSORS.get(key)
            if cfg and key in self.sensors:
                delay = 200 + (i * 200)
                self.root.after(
                    delay,
                    lambda k=key, ms=cfg["interval_ms"]: self._schedule_poll(
                        k, ms
                    ),
                )

        self._update_status_bar()
        self._schedule_log_flush()
        logger.info("Dashboard polling started.")

    def _schedule_poll(self, key, interval_ms):
        """Poll sensor in background thread, post results to main thread."""
        sensor = self.sensors.get(key)
        if not sensor:
            return

        def _do_read():
            try:
                return sensor.read(demo=self.demo_mode)
            except Exception as exc:
                logger.error("Poll error for %s: %s", key, exc)
                return None

        def _on_result(readings):
            if readings:
                self.reading_count += 1
                for field, value in readings.items():
                    hist = self.histories.get(key, {}).get(field)
                    if hist is not None:
                        if isinstance(value, bool):
                            hist.append(1 if value else 0)
                        elif isinstance(value, (int, float)):
                            hist.append(value)
                self._update_cards(key, readings)
                if self.logging_active:
                    self._buffer_readings(key, readings)
            self.root.after(
                interval_ms, lambda: self._schedule_poll(key, interval_ms)
            )

        def _threaded_read():
            readings = _do_read()
            self.root.after(0, lambda: _on_result(readings))

        t = threading.Thread(target=_threaded_read, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    # Card updates
    # ------------------------------------------------------------------

    def _update_cards(self, sensor_key, readings):
        """Update all cards that show data from this sensor."""
        for card in self._cards:
            if card._sensor_key != sensor_key:
                continue

            field_key = card._field_key
            value = readings.get(field_key)
            if value is None:
                continue

            # Value label with threshold coloring
            try:
                text = card._format.format(value)
            except (ValueError, TypeError):
                text = str(value)

            # Pick color from thresholds if defined
            active_color = card._color
            threshold_idx = 0
            if card._thresholds and isinstance(value, (int, float)):
                for i, (threshold_val, threshold_color) in enumerate(
                    card._thresholds
                ):
                    if value <= threshold_val:
                        active_color = threshold_color
                        threshold_idx = i
                        break

            card._value_lbl.config(text=text, fg=active_color)

            # Alert border: glow when at extreme thresholds
            n_thresh = len(card._thresholds)
            if n_thresh >= 3 and (
                threshold_idx == 0 or threshold_idx >= n_thresh - 1
            ):
                card.config(
                    highlightbackground=active_color, highlightthickness=2
                )
            else:
                card.config(
                    highlightbackground=THEME["accent"],
                    highlightthickness=1,
                )

            # Status dot
            sensor = self.sensors.get(sensor_key)
            if self.demo_mode:
                card._status_dot.config(
                    text="\u25c9", fg=THEME["warning"]
                )
            elif sensor and not sensor.simulated:
                card._status_dot.config(
                    text="\u25cf", fg=THEME["success"]
                )
            else:
                card._status_dot.config(
                    text="\u25cb", fg=THEME["text_dim"]
                )

            # Sparkline (uses threshold color for current value)
            history = self.histories.get(sensor_key, {}).get(
                field_key, deque()
            )
            self._draw_sparkline(card._spark, list(history), active_color)

            # Stats
            data = list(history)
            if len(data) >= 2:
                mn, mx = min(data), max(data)
                u = card._unit
                card._stats_lbl.config(text=f"min {mn:.1f}{u}  max {mx:.1f}{u}")

    def _draw_sparkline(self, canvas, data, color):
        """Draw a minimal sparkline on a small canvas."""
        canvas.delete("all")
        if len(data) < 2:
            return

        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 20 or h < 10:
            return

        px = 4
        py = 4
        pw = w - 2 * px
        ph = h - 2 * py

        d_min = min(data)
        d_max = max(data)
        d_range = d_max - d_min if d_max != d_min else 1

        n = len(data)
        points = []
        for i, val in enumerate(data):
            x = px + (i / (n - 1)) * pw
            y = py + (1.0 - (val - d_min) / d_range) * ph
            points.append((x, y))

        # Fill under the line
        fill_pts = list(points) + [
            (points[-1][0], h - py),
            (points[0][0], h - py),
        ]
        flat = []
        for fx, fy in fill_pts:
            flat.extend([fx, fy])
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            fill_color = f"#{r // 5:02x}{g // 5:02x}{b // 5:02x}"
        except (ValueError, IndexError):
            fill_color = "#111111"
        canvas.create_polygon(flat, fill=fill_color, outline="")

        # Line trace
        for i in range(len(points) - 1):
            canvas.create_line(
                points[i][0],
                points[i][1],
                points[i + 1][0],
                points[i + 1][1],
                fill=color,
                width=2,
            )

        # Current value dot
        lx, ly = points[-1]
        canvas.create_oval(
            lx - 3, ly - 3, lx + 3, ly + 3, fill=color, outline=""
        )

    # ------------------------------------------------------------------
    # Detail overlay (tap card to expand)
    # ------------------------------------------------------------------

    def _show_detail(self, card, kiosk=False):
        """Show full-screen detail overlay for a tapped card."""
        sensor_key = card._sensor_key
        field_key = card._field_key
        color = card._color
        unit = card._unit
        label = card._label_text
        fmt = card._format

        # Current value and threshold color
        history = list(
            self.histories.get(sensor_key, {}).get(field_key, deque())
        )
        current = history[-1] if history else None
        active_color = color
        if card._thresholds and current is not None:
            for threshold_val, threshold_color in card._thresholds:
                if current <= threshold_val:
                    active_color = threshold_color
                    break

        # Overlay frame
        overlay = tk.Frame(self.root, bg=THEME["bg"])
        overlay.place(x=0, y=0, relwidth=1.0, relheight=1.0)

        if kiosk:
            self._kiosk_overlay = overlay

        # Tap anywhere to dismiss (also stops kiosk)
        def dismiss(e=None):
            if self.kiosk_mode:
                self._toggle_kiosk()
            overlay.destroy()
            self._kiosk_overlay = None

        overlay.bind("<Button-1>", dismiss)

        # Header: label + dismiss hint
        hdr = tk.Frame(overlay, bg=THEME["bg"])
        hdr.pack(fill="x", padx=16, pady=(16, 0))
        hdr.bind("<Button-1>", dismiss)

        tk.Label(
            hdr,
            text=label,
            font=("Arial", 18, "bold"),
            bg=THEME["bg"],
            fg=THEME["text"],
        ).pack(side="left")

        tk.Label(
            hdr,
            text="tap to close",
            font=("Arial", 10),
            bg=THEME["bg"],
            fg=THEME["text_dim"],
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
            val_frame,
            text=val_text,
            font=("Arial", 64, "bold"),
            bg=THEME["bg"],
            fg=active_color,
        )
        val_lbl.pack(side="left")
        val_lbl.bind("<Button-1>", dismiss)

        unit_lbl = tk.Label(
            val_frame,
            text=f" {unit}",
            font=("Arial", 24),
            bg=THEME["bg"],
            fg=THEME["text_dim"],
        )
        unit_lbl.pack(side="left", anchor="s", pady=(0, 10))
        unit_lbl.bind("<Button-1>", dismiss)

        # Full-width graph
        graph = tk.Canvas(
            overlay,
            bg=THEME["graph_bg"],
            height=200,
            highlightthickness=0,
        )
        graph.pack(fill="x", padx=16, pady=(12, 8))
        graph.bind("<Button-1>", dismiss)

        # Draw graph after layout
        overlay.update_idletasks()
        self._draw_detail_graph(graph, history, active_color, unit, fmt)

        # Stats row
        stats = tk.Frame(overlay, bg=THEME["bg"])
        stats.pack(fill="x", padx=16, pady=(0, 8))
        stats.bind("<Button-1>", dismiss)

        if len(history) >= 2:
            mn = min(history)
            mx = max(history)
            avg = sum(history) / len(history)
            for stat_label, stat_val in [
                ("MIN", mn),
                ("AVG", avg),
                ("MAX", mx),
            ]:
                sf = tk.Frame(stats, bg=THEME["bg"])
                sf.pack(side="left", expand=True)
                sf.bind("<Button-1>", dismiss)

                s_val = tk.Label(
                    sf,
                    text=fmt.format(stat_val),
                    font=("Arial", 20, "bold"),
                    bg=THEME["bg"],
                    fg=THEME["text"],
                )
                s_val.pack()
                s_val.bind("<Button-1>", dismiss)

                s_lbl = tk.Label(
                    sf,
                    text=stat_label,
                    font=("Arial", 9),
                    bg=THEME["bg"],
                    fg=THEME["text_dim"],
                )
                s_lbl.pack()
                s_lbl.bind("<Button-1>", dismiss)

        # Readings count
        count_lbl = tk.Label(
            overlay,
            text=f"{len(history)} readings",
            font=("Arial", 10),
            bg=THEME["bg"],
            fg=THEME["text_dim"],
        )
        count_lbl.pack(pady=(4, 0))
        count_lbl.bind("<Button-1>", dismiss)

    def _draw_detail_graph(self, canvas, data, color, unit, fmt):
        """Draw a larger graph with axis labels for the detail overlay."""
        if len(data) < 2:
            canvas.create_text(
                canvas.winfo_width() // 2,
                canvas.winfo_height() // 2,
                text="Collecting data...",
                fill=THEME["text_dim"],
                font=("Arial", 12),
            )
            return

        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 40 or h < 40:
            return

        # Margins for axis labels
        left = 52
        right = 12
        top_m = 12
        bot = 24
        pw = w - left - right
        ph = h - top_m - bot

        d_min = min(data)
        d_max = max(data)
        d_range = d_max - d_min if d_max != d_min else 1

        # Grid lines (3 horizontal)
        for i in range(4):
            y = top_m + (i / 3) * ph
            val = d_max - (i / 3) * d_range
            canvas.create_line(
                left, y, w - right, y, fill="#333", dash=(2, 4)
            )
            try:
                label = fmt.format(val)
            except (ValueError, TypeError):
                label = f"{val:.1f}"
            canvas.create_text(
                left - 6, y, text=label, anchor="e",
                fill=THEME["text_dim"], font=("Arial", 8),
            )

        # Data points
        n = len(data)
        points = []
        for i, val in enumerate(data):
            x = left + (i / (n - 1)) * pw
            y = top_m + (1.0 - (val - d_min) / d_range) * ph
            points.append((x, y))

        # Fill under curve
        fill_pts = list(points) + [
            (points[-1][0], top_m + ph),
            (points[0][0], top_m + ph),
        ]
        flat = []
        for fx, fy in fill_pts:
            flat.extend([fx, fy])
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            fill_color = f"#{r // 4:02x}{g // 4:02x}{b // 4:02x}"
        except (ValueError, IndexError):
            fill_color = "#111111"
        canvas.create_polygon(flat, fill=fill_color, outline="")

        # Line
        for i in range(len(points) - 1):
            canvas.create_line(
                points[i][0], points[i][1],
                points[i + 1][0], points[i + 1][1],
                fill=color, width=2,
            )

        # Current value dot
        lx, ly = points[-1]
        canvas.create_oval(
            lx - 4, ly - 4, lx + 4, ly + 4, fill=color, outline=""
        )

    # ------------------------------------------------------------------
    # Clock + status bar
    # ------------------------------------------------------------------

    def _update_clock(self):
        self._clock_lbl.config(text=datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000, self._update_clock)

    def _update_status_bar(self):
        live = sum(1 for s in self.sensors.values() if not s.simulated)
        total = len(self.sensors)
        mode = "DEMO" if self.demo_mode else "LIVE"
        self._status_lbl.config(
            text=f"{live}/{total} sensors  \u2502  {mode}"
        )
        self._count_lbl.config(text=f"Readings: {self.reading_count}")
        self.root.after(2000, self._update_status_bar)

    # ------------------------------------------------------------------
    # Demo mode
    # ------------------------------------------------------------------

    def _toggle_demo(self):
        self.demo_mode = not self.demo_mode
        if self.demo_mode:
            self._demo_btn.config(bg=THEME["warning"], fg="#000")
        else:
            self._demo_btn.config(bg=THEME["accent"], fg="white")

    # ------------------------------------------------------------------
    # Kiosk / ambient mode
    # ------------------------------------------------------------------

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
        """Show next card detail, then schedule the next switch."""
        if not self.kiosk_mode or not self._cards:
            return

        # Dismiss previous overlay
        if self._kiosk_overlay:
            self._kiosk_overlay.destroy()
            self._kiosk_overlay = None

        card = self._cards[self._kiosk_idx % len(self._cards)]
        self._kiosk_idx = (self._kiosk_idx + 1) % len(self._cards)
        self._show_detail(card, kiosk=True)

        self.root.after(self._kiosk_interval, self._kiosk_cycle)

    # ------------------------------------------------------------------
    # CSV logging (batched writes)
    # ------------------------------------------------------------------

    def _toggle_logging(self):
        if not self.logging_active:
            os.makedirs(LOG_DIR, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file = os.path.join(LOG_DIR, f"sensor_log_{ts}.csv")
            with open(self.log_file, "w", newline="") as f:
                csv.writer(f).writerow(
                    ["timestamp", "sensor", "field", "value"]
                )
            self.logging_active = True
            self._log_btn.config(bg=THEME["error"], text="STOP")
        else:
            self._flush_log_buffer()
            self.logging_active = False
            self._log_btn.config(bg=THEME["accent"], text="LOG")

    def _buffer_readings(self, key, readings):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        for field, value in readings.items():
            self.log_buffer.append([ts, key, field, value])

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

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _toggle_fullscreen(self, event=None):
        current = self.root.attributes("-fullscreen")
        self.root.attributes("-fullscreen", not current)

    def cleanup(self):
        """Release all sensor hardware resources."""
        self._flush_log_buffer()
        for sensor in self.sensors.values():
            sensor.close()
