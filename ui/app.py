"""Main GUI application for Sensor Playground.

Designed for 800x480 touchscreen (Freenove 7" DSI).
Dark theme, large touch targets, category-grouped sensor navigation.

Layout (800 x 480):
  +-------------------------------------------------+
  |  SENSOR PLAYGROUND          [DEMO] [LOG]  [X]  |  50px
  +--------+--------+--------+--------+--------+----+
  | Enviro | Motion |Light&IR| Sound  |Output  |Anlg|  38px category bar
  +--------+--------+--------+--------+--------+----+
  | >> DHT11  |  >> DS18B20  | >> Soil             |  32px sensor bar
  +-------------------------------------------------+
  |                                                 |
  |   Value display (left)    Graph (right)         |  ~325px
  |   Stats / wiring hint                           |
  |                                                 |
  +-------------------------------------------------+
  |  Status message                    Readings: N  |  35px
  +-------------------------------------------------+

Improvements over initial version:
  - Min/max/avg statistics per field
  - Graph fill gradient under line traces
  - Sensor health/reliability indicator
  - System info panel (CPU temp, memory, uptime)
  - Batched CSV logging to reduce SD card writes
  - Auto-demo kiosk mode (cycles through sensors)
  - Configurable logging via proper logging module
"""

import tkinter as tk
from collections import deque
from datetime import datetime
import csv
import os
import logging
import time
import threading

from config import SENSORS, CATEGORIES, THEME, MAX_HISTORY, LOG_DIR
from sensors import SENSOR_CLASSES

logger = logging.getLogger(__name__)


class SensorPlayground:
    def __init__(self, root):
        self.root = root
        self.root.title("Sensor Playground")
        self.root.configure(bg=THEME["bg"])
        self.root.attributes("-fullscreen", True)

        # Escape toggles fullscreen (useful during development)
        self.root.bind("<Escape>", self._toggle_fullscreen)

        # State
        self.demo_mode = False
        self.logging_active = False
        self.log_file = None
        self.log_buffer = []           # batched CSV rows
        self.log_flush_interval = 5000 # ms between flushes
        self.reading_count = 0
        self.active_category = None
        self.active_tab = None
        self.kiosk_mode = False
        self._kiosk_after_id = None

        # Build category -> sensor mapping (only categories with registered sensors)
        self._cat_sensors = {}  # {cat_key: [sensor_key, ...]}
        for key, cfg in SENSORS.items():
            cat = cfg.get("category", "environment")
            if cat not in self._cat_sensors:
                self._cat_sensors[cat] = []
            self._cat_sensors[cat].append(key)

        # Ordered categories (only those with sensors)
        self._cat_order = [c for c in CATEGORIES if c in self._cat_sensors]

        # Initialise sensors and per-field history buffers
        logger.info("Initialising sensors...")
        self.sensors = {}
        self.histories = {}
        for key, cfg in SENSORS.items():
            cls = SENSOR_CLASSES.get(key)
            if cls:
                logger.debug("  init %s ...", key)
                self.sensors[key] = cls(cfg["pin"], cfg)
                self.histories[key] = {
                    field: deque(maxlen=MAX_HISTORY)
                    for field in cfg["fields"]
                }
        logger.info("Sensors ready (%d loaded).", len(self.sensors))

        # OLED display disabled (not needed for touchscreen HAT)
        self._oled = None

        # Build the interface
        logger.info("Building UI...")
        self._build_top_bar()
        self._build_category_bar()
        self._build_sensor_bar()
        self._build_content_area()
        self._build_status_bar()
        logger.info("UI built.")

        # Defer ALL startup work until after mainloop is running.
        # Previously _schedule_poll was called directly here, which
        # caused synchronous reads of ALL sensors before the window
        # appeared — hanging the app for 10+ seconds (or forever if
        # an I2C read blocked).
        def initialize_app():
            # Select first category
            if self._cat_order:
                self._switch_category(self._cat_order[0])
            # Start UI counter update
            self._update_counter()
            # Start log flush timer
            self._schedule_log_flush()
            # Start polling sensors — staggered so they don't all
            # fire simultaneously and cause I2C bus contention
            for i, (key, cfg) in enumerate(SENSORS.items()):
                if key in self.sensors:
                    delay = 300 + (i * 150)
                    self.root.after(
                        delay,
                        lambda k=key, ms=cfg["interval_ms"]: self._schedule_poll(k, ms),
                    )
            logger.info("Sensor polling started (staggered).")

        self.root.after(100, initialize_app)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_top_bar(self):
        bar = tk.Frame(self.root, bg=THEME["bg"], height=50)
        bar.pack(fill="x", padx=10, pady=(8, 0))
        bar.pack_propagate(False)

        tk.Label(
            bar, text="SENSOR PLAYGROUND",
            font=("Arial", 18, "bold"),
            bg=THEME["bg"], fg=THEME["text"],
        ).pack(side="left")

        # Buttons (right-aligned, reverse order)
        btn_style = {"font": ("Arial", 11, "bold"), "relief": "flat",
                     "width": 6, "cursor": "hand2"}

        self._exit_btn = tk.Button(
            bar, text="EXIT", bg="#444", fg="white",
            command=self.root.quit, **btn_style,
        )
        self._exit_btn.pack(side="right", padx=4)

        self._log_btn = tk.Button(
            bar, text="LOG", bg=THEME["accent"], fg="white",
            command=self._toggle_logging, **btn_style,
        )
        self._log_btn.pack(side="right", padx=4)

        self._demo_btn = tk.Button(
            bar, text="DEMO", bg=THEME["accent"], fg="white",
            command=self._toggle_demo, **btn_style,
        )
        self._demo_btn.pack(side="right", padx=4)

    def _build_category_bar(self):
        """Top row: category buttons (Environment, Motion, etc)."""
        self._cat_bar = tk.Frame(self.root, bg=THEME["bg"], height=38)
        self._cat_bar.pack(fill="x", padx=10, pady=(6, 0))
        self._cat_bar.pack_propagate(False)

        self._cat_buttons = {}
        for cat_key in self._cat_order:
            cat_cfg = CATEGORIES[cat_key]
            btn = tk.Button(
                self._cat_bar, text=cat_cfg["label"],
                font=("Arial", 11, "bold"),
                bg=THEME["card_bg"], fg=THEME["text_dim"],
                relief="flat", bd=0, cursor="hand2",
                command=lambda k=cat_key: self._switch_category(k),
            )
            btn.pack(side="left", padx=2, fill="both", expand=True)
            self._cat_buttons[cat_key] = btn

        # SYSTEM button at the end
        sys_btn = tk.Button(
            self._cat_bar, text="SYSTEM",
            font=("Arial", 11, "bold"),
            bg=THEME["card_bg"], fg=THEME["text_dim"],
            relief="flat", bd=0, cursor="hand2",
            command=lambda: self._switch_to_system(),
        )
        sys_btn.pack(side="left", padx=2, fill="both", expand=True)
        self._cat_buttons["system"] = sys_btn

        # INFO button at the end
        info_btn = tk.Button(
            self._cat_bar, text="INFO",
            font=("Arial", 11, "bold"),
            bg=THEME["card_bg"], fg=THEME["text_dim"],
            relief="flat", bd=0, cursor="hand2",
            command=lambda: self._switch_to_info(),
        )
        info_btn.pack(side="left", padx=2, fill="both", expand=True)
        self._cat_buttons["info"] = info_btn

    def _build_sensor_bar(self):
        """Bottom row: sensor sub-tabs within current category."""
        self._sensor_bar = tk.Frame(self.root, bg=THEME["bg"], height=32)
        self._sensor_bar.pack(fill="x", padx=10, pady=(2, 0))
        self._sensor_bar.pack_propagate(False)

        self._sensor_buttons = {}

    def _populate_sensor_bar(self, cat_key):
        """Clear and rebuild sensor sub-tabs for a category."""
        for widget in self._sensor_bar.winfo_children():
            widget.destroy()
        self._sensor_buttons = {}

        if cat_key in ("info", "system") or cat_key not in self._cat_sensors:
            return

        for sensor_key in self._cat_sensors[cat_key]:
            cfg = SENSORS[sensor_key]
            sensor = self.sensors.get(sensor_key)
            dot = "\u25cf" if (sensor and not sensor.simulated) else "\u25cb"
            label = f"{dot} {cfg['label']}"

            btn = tk.Button(
                self._sensor_bar, text=label,
                font=("Arial", 10, "bold"),
                bg=THEME["card_bg"], fg=THEME["text_dim"],
                relief="flat", bd=0, cursor="hand2",
                command=lambda k=sensor_key: self._switch_tab(k),
            )
            btn.pack(side="left", padx=2, fill="both", expand=True)
            self._sensor_buttons[sensor_key] = btn

    def _build_content_area(self):
        self._content = tk.Frame(self.root, bg=THEME["card_bg"])
        self._content.pack(fill="both", expand=True, padx=10, pady=8)

        self._tab_frames = {}
        for key in SENSORS:
            self._tab_frames[key] = self._build_sensor_frame(key)
        self._tab_frames["info"] = self._build_info_frame()
        self._tab_frames["system"] = self._build_system_frame()

    def _build_sensor_frame(self, key):
        """Build the display frame for one sensor tab."""
        cfg = SENSORS[key]
        sensor = self.sensors.get(key)

        frame = tk.Frame(self._content, bg=THEME["card_bg"])

        # ---- Left panel: values + status (fixed width) ----
        left = tk.Frame(frame, bg=THEME["card_bg"], width=260)
        left.pack(side="left", fill="y", padx=(15, 5), pady=10)
        left.pack_propagate(False)

        tk.Label(
            left, text=cfg["description"],
            font=("Arial", 13), bg=THEME["card_bg"], fg=THEME["text_dim"],
        ).pack(anchor="w", pady=(5, 0))

        # Value labels for each data field
        frame._value_labels = {}
        frame._stat_labels = {}
        for field_key, field_cfg in cfg["fields"].items():
            val_lbl = tk.Label(
                left, text="--",
                font=("Arial", 34, "bold"),
                bg=THEME["card_bg"], fg=field_cfg["color"],
            )
            val_lbl.pack(anchor="w", pady=(12, 0))

            suffix = f"  {field_cfg['unit']}" if field_cfg["unit"] else ""
            tk.Label(
                left, text=field_cfg["label"] + suffix,
                font=("Arial", 11), bg=THEME["card_bg"], fg=THEME["text_dim"],
            ).pack(anchor="w")

            frame._value_labels[field_key] = val_lbl

            # Statistics label (min / max / avg)
            stat_lbl = tk.Label(
                left, text="",
                font=("Arial", 9), bg=THEME["card_bg"], fg=THEME["text_dim"],
            )
            stat_lbl.pack(anchor="w", pady=(2, 0))
            frame._stat_labels[field_key] = stat_lbl

        # Status line
        if sensor and not sensor.simulated:
            s_text, s_color = "\u25cf LIVE", THEME["success"]
        else:
            s_text, s_color = "\u25cb NOT CONNECTED", THEME["text_dim"]

        frame._status_lbl = tk.Label(
            left, text=s_text,
            font=("Arial", 11, "bold"),
            bg=THEME["card_bg"], fg=s_color,
        )
        frame._status_lbl.pack(anchor="w", pady=(15, 0))

        # Reliability label
        frame._reliability_lbl = tk.Label(
            left, text="",
            font=("Arial", 9), bg=THEME["card_bg"], fg=THEME["text_dim"],
        )
        frame._reliability_lbl.pack(anchor="w", pady=(2, 0))

        # Wiring hint (shown when not connected)
        wiring_text = "  \n".join(cfg.get("wiring", []))
        frame._wiring_lbl = tk.Label(
            left, text=wiring_text,
            font=("Courier", 9), bg=THEME["card_bg"], fg=THEME["text_dim"],
            justify="left",
        )
        frame._wiring_lbl.pack(anchor="w", pady=(8, 0))

        # ---- Right panel: graph canvas ----
        right = tk.Frame(frame, bg=THEME["card_bg"])
        right.pack(side="right", fill="both", expand=True, padx=(5, 15), pady=10)

        canvas = tk.Canvas(
            right, bg=THEME["graph_bg"],
            highlightthickness=1, highlightbackground=THEME["accent"],
        )
        canvas.pack(fill="both", expand=True)
        frame._canvas = canvas

        # Touch canvas to clear data for this sensor
        canvas.bind("<Button-1>", lambda e, k=key: self._clear_history(k))

        return frame

    def _build_info_frame(self):
        """Build the INFO tab showing wiring reference and GPIO map."""
        frame = tk.Frame(self._content, bg=THEME["card_bg"])

        text = tk.Text(
            frame, bg=THEME["card_bg"], fg=THEME["text"],
            font=("Courier", 10), relief="flat",
            wrap="word", padx=20, pady=15,
            highlightthickness=0,
        )
        # Add scrollbar
        scrollbar = tk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)

        lines = []
        lines.append("SENSOR WIRING REFERENCE")
        lines.append("=" * 52)
        lines.append("")

        # GPIO pin map (physical header layout — extended)
        lines.append("Raspberry Pi GPIO Header (top-down view):")
        lines.append("-" * 52)

        # Build used-pins lookup
        used_pins = {}
        for key, cfg in SENSORS.items():
            pin = cfg.get("pin", -1)
            if pin >= 0:
                used_pins[pin] = cfg["label"]
            for ep in cfg.get("extra_pins", []):
                used_pins[ep] = cfg["label"]

        # BCM -> physical pin mapping (all 40 pins)
        bcm_to_phys = {
            2: 3, 3: 5, 4: 7, 14: 8, 15: 10, 17: 11, 18: 12, 27: 13,
            22: 15, 23: 16, 24: 18, 10: 19, 9: 21, 25: 22, 11: 23,
            8: 24, 7: 26, 0: 27, 1: 28, 5: 29, 6: 31, 12: 32, 13: 33,
            19: 35, 16: 36, 26: 37, 20: 38, 21: 40,
        }
        phys_to_bcm = {v: k for k, v in bcm_to_phys.items()}

        power_pins = {1: "3.3V", 2: "5V", 4: "5V", 6: "GND", 9: "GND",
                      14: "GND", 17: "3.3V", 20: "GND", 25: "GND",
                      30: "GND", 34: "GND", 39: "GND"}
        reserved = {2: "SDA", 3: "SCL", 7: "CE1", 8: "CE0", 9: "MISO",
                    10: "MOSI", 11: "SCLK", 14: "TXD", 15: "RXD"}

        for row in range(1, 40, 2):
            left_phys = row
            right_phys = row + 1

            def pin_str(phys):
                if phys in power_pins:
                    return power_pins[phys]
                bcm = phys_to_bcm.get(phys)
                if bcm is None:
                    return f"Pin {phys}"
                if bcm in used_pins:
                    return f"GPIO {bcm} << {used_pins[bcm]}"
                if bcm in reserved:
                    return f"GPIO {bcm} [{reserved[bcm]}]"
                return f"GPIO {bcm} (free)"

            lines.append(
                f"  {pin_str(left_phys):>26s}  [{left_phys:>2d}|{right_phys:<2d}]"
                f"  {pin_str(right_phys)}"
            )
        lines.append("")

        # Per-sensor wiring (grouped by category)
        for cat_key in CATEGORIES:
            cat_sensors = [k for k, c in SENSORS.items() if c.get("category") == cat_key]
            if not cat_sensors:
                continue
            lines.append(f"--- {CATEGORIES[cat_key]['label'].upper()} ---")
            for key in cat_sensors:
                cfg = SENSORS[key]
                lines.append(f"  {cfg['label']} - {cfg['description']}")
                for w in cfg.get("wiring", []):
                    lines.append(f"    {w}")
                if cfg.get("notes"):
                    lines.append(f"    Note: {cfg['notes']}")
                lines.append("")

        lines.append("KEYBOARD SHORTCUTS")
        lines.append("-" * 52)
        lines.append("  Escape     Toggle fullscreen")
        lines.append("  DEMO btn   Toggle simulated data")
        lines.append("  LOG btn    Start/stop CSV logging")
        lines.append("  Tap graph  Clear sensor history")
        lines.append("")
        lines.append("TIPS")
        lines.append("-" * 52)
        lines.append("- Use female-to-female Dupont wires for modules")
        lines.append("- DHT11 needs 3.3V; PIR and Sound need 5V")
        lines.append("- Wire one sensor at a time, test, then add next")
        lines.append("- Tap DEMO button to see simulated data")
        lines.append("- GPIO scanner: python3 tools/gpio_scanner.py")

        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")

        return frame

    def _build_system_frame(self):
        """Build the SYSTEM tab showing Pi health and sensor overview."""
        frame = tk.Frame(self._content, bg=THEME["card_bg"])

        text = tk.Text(
            frame, bg=THEME["card_bg"], fg=THEME["text"],
            font=("Courier", 10), relief="flat",
            wrap="word", padx=20, pady=15,
            highlightthickness=0,
        )
        scrollbar = tk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)

        frame._text = text
        self._update_system_info(frame)
        return frame

    def _update_system_info(self, frame=None):
        """Refresh the system info panel."""
        if frame is None:
            frame = self._tab_frames.get("system")
        if frame is None:
            return

        text = frame._text
        text.configure(state="normal")
        text.delete("1.0", "end")

        lines = []
        lines.append("SYSTEM INFORMATION")
        lines.append("=" * 52)
        lines.append("")

        # CPU temperature
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                cpu_temp = int(f.read().strip()) / 1000.0
            lines.append(f"  CPU Temperature:  {cpu_temp:.1f} \u00b0C")
        except Exception:
            lines.append("  CPU Temperature:  unavailable")

        # Memory
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = {}
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        meminfo[parts[0].strip()] = parts[1].strip()
            total = int(meminfo.get("MemTotal", "0 kB").split()[0]) // 1024
            avail = int(meminfo.get("MemAvailable", "0 kB").split()[0]) // 1024
            used = total - avail
            pct = (used / total * 100) if total > 0 else 0
            lines.append(f"  Memory:           {used} / {total} MB ({pct:.0f}%)")
        except Exception:
            lines.append("  Memory:           unavailable")

        # Uptime
        try:
            with open("/proc/uptime", "r") as f:
                uptime_sec = float(f.read().split()[0])
            hours = int(uptime_sec // 3600)
            minutes = int((uptime_sec % 3600) // 60)
            lines.append(f"  Uptime:           {hours}h {minutes}m")
        except Exception:
            lines.append("  Uptime:           unavailable")

        # Disk usage
        try:
            st = os.statvfs("/")
            total_gb = (st.f_blocks * st.f_frsize) / (1024**3)
            free_gb = (st.f_bavail * st.f_frsize) / (1024**3)
            used_gb = total_gb - free_gb
            lines.append(f"  Disk:             {used_gb:.1f} / {total_gb:.1f} GB")
        except Exception:
            lines.append("  Disk:             unavailable")

        lines.append("")
        lines.append("SENSOR STATUS")
        lines.append("-" * 52)
        lines.append(f"  {'Sensor':<16} {'Status':<14} {'Reliability':>11}")
        lines.append(f"  {'─'*16} {'─'*14} {'─'*11}")

        live_count = 0
        for key, cfg in SENSORS.items():
            sensor = self.sensors.get(key)
            if sensor:
                if self.demo_mode:
                    status = "DEMO"
                elif not sensor.simulated:
                    status = "LIVE"
                    live_count += 1
                else:
                    status = "OFFLINE"
                rel = f"{sensor.reliability:.0f}%"
            else:
                status = "N/A"
                rel = "--"
            lines.append(f"  {cfg['label']:<16} {status:<14} {rel:>11}")

        lines.append("")
        lines.append(f"  Total sensors: {len(SENSORS)}")
        lines.append(f"  Live:          {live_count}")
        lines.append(f"  Readings:      {self.reading_count}")
        if self.logging_active and self.log_file:
            lines.append(f"  Logging to:    {self.log_file}")

        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")

        # Refresh every 5 seconds if system tab is visible
        if self.active_tab == "system":
            self.root.after(5000, lambda: self._update_system_info())

    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg=THEME["bg"], height=32)
        bar.pack(fill="x", padx=10, pady=(0, 6))
        bar.pack_propagate(False)

        self._status_lbl = tk.Label(
            bar, text="Ready  \u2502  Tap DEMO for simulated data",
            font=("Arial", 10), bg=THEME["bg"], fg=THEME["text_dim"],
        )
        self._status_lbl.pack(side="left")

        self._count_lbl = tk.Label(
            bar, text="Readings: 0",
            font=("Arial", 10), bg=THEME["bg"], fg=THEME["text_dim"],
        )
        self._count_lbl.pack(side="right")

    # ------------------------------------------------------------------
    # Category + tab switching
    # ------------------------------------------------------------------

    def _switch_category(self, cat_key):
        """Select a category, populate sensor bar, auto-select first sensor."""
        self.active_category = cat_key

        # Highlight active category button
        for k, btn in self._cat_buttons.items():
            if k == cat_key:
                cat_color = CATEGORIES.get(cat_key, {}).get("color", THEME["accent"])
                btn.configure(bg=cat_color, fg="#1a1a2e")
            else:
                btn.configure(bg=THEME["card_bg"], fg=THEME["text_dim"])

        # Populate sensor sub-bar
        self._populate_sensor_bar(cat_key)

        # Auto-select first sensor in category
        sensors_in_cat = self._cat_sensors.get(cat_key, [])
        if sensors_in_cat:
            self._switch_tab(sensors_in_cat[0])

    def _switch_to_info(self):
        """Switch to the INFO tab."""
        self.active_category = "info"
        self.active_tab = "info"

        for k, btn in self._cat_buttons.items():
            if k == "info":
                btn.configure(bg=THEME["accent"], fg="white")
            else:
                btn.configure(bg=THEME["card_bg"], fg=THEME["text_dim"])

        self._populate_sensor_bar("info")

        for k, frame in self._tab_frames.items():
            if k == "info":
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

    def _switch_to_system(self):
        """Switch to the SYSTEM tab."""
        self.active_category = "system"
        self.active_tab = "system"

        for k, btn in self._cat_buttons.items():
            if k == "system":
                btn.configure(bg=THEME["accent"], fg="white")
            else:
                btn.configure(bg=THEME["card_bg"], fg=THEME["text_dim"])

        self._populate_sensor_bar("system")

        for k, frame in self._tab_frames.items():
            if k == "system":
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

        self._update_system_info()

    def _switch_tab(self, key):
        """Select a specific sensor tab."""
        self.active_tab = key

        # Highlight active sensor button
        for k, btn in self._sensor_buttons.items():
            if k == key:
                btn.configure(bg=THEME["accent"], fg="white")
            else:
                btn.configure(bg=THEME["card_bg"], fg=THEME["text_dim"])

        # Show the selected sensor frame, hide others
        for k, frame in self._tab_frames.items():
            if k == key:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

        # Redraw graph for newly visible tab
        self._draw_graph(key)

    # ------------------------------------------------------------------
    # Sensor polling
    # ------------------------------------------------------------------

    def _schedule_poll(self, key, interval_ms):
        """Poll a sensor in a background thread, then process on main thread.

        Sensor reads (especially I2C) can take seconds and must not block
        the tkinter event loop. The read runs in a daemon thread; when it
        finishes, results are posted back to the main thread via root.after().
        """
        sensor = self.sensors.get(key)
        if not sensor:
            return

        def _do_read():
            """Run in background thread — performs the blocking read."""
            try:
                return sensor.read(demo=self.demo_mode)
            except Exception as exc:
                logger.error("Poll error for %s: %s", key, exc)
                return None

        def _on_result(readings):
            """Run on main thread — updates UI and schedules next poll."""
            if readings:
                self.reading_count += 1

                # Store in history
                for field, value in readings.items():
                    if field in self.histories[key]:
                        if isinstance(value, bool):
                            self.histories[key][field].append(1 if value else 0)
                        elif isinstance(value, str):
                            self.histories[key][field].append(hash(value) % 8)
                        else:
                            self.histories[key][field].append(value)

                # Update display if this sensor's tab is visible
                if self.active_tab == key:
                    self._update_sensor_display(key, readings)

                # Update OLED if available
                if self._oled:
                    try:
                        self._oled.update(SENSORS[key]["label"], readings)
                    except Exception:
                        pass

                # CSV logging (batched)
                if self.logging_active:
                    self._buffer_readings(key, readings)

            # Schedule next poll (only after current read completes)
            self.root.after(interval_ms, lambda: self._schedule_poll(key, interval_ms))

        def _threaded_read():
            readings = _do_read()
            # Post result back to main thread for safe UI updates
            self.root.after(0, lambda: _on_result(readings))

        t = threading.Thread(target=_threaded_read, daemon=True)
        t.start()

    def _update_sensor_display(self, key, readings):
        """Update value labels, status, statistics, and graph for a sensor tab."""
        frame = self._tab_frames.get(key)
        if not frame:
            return

        cfg = SENSORS[key]
        sensor = self.sensors.get(key)

        # Update value labels
        for field, value in readings.items():
            lbl = frame._value_labels.get(field)
            if not lbl:
                continue
            if isinstance(value, bool):
                text = "YES" if value else "NO"
            elif isinstance(value, float):
                text = f"{value:.1f}"
            else:
                text = str(value)
            lbl.config(text=text)

        # Update statistics
        for field_key in cfg["fields"]:
            stat_lbl = frame._stat_labels.get(field_key)
            history = self.histories[key].get(field_key, deque())
            if stat_lbl and len(history) >= 2:
                data = list(history)
                field_cfg = cfg["fields"][field_key]
                mode = field_cfg.get("graph_mode", "line")
                if mode == "line":
                    mn, mx, avg = min(data), max(data), sum(data) / len(data)
                    stat_lbl.config(
                        text=f"min {mn:.1f}  max {mx:.1f}  avg {avg:.1f}"
                    )
                else:
                    # For step/boolean fields, show trigger count
                    triggers = sum(1 for v in data if v > 0.5)
                    stat_lbl.config(text=f"{triggers} triggers / {len(data)} samples")

        # Update status indicator
        if self.demo_mode:
            frame._status_lbl.config(text="\u25c9 DEMO", fg=THEME["warning"])
            frame._wiring_lbl.config(fg=THEME["card_bg"])  # hide wiring
        elif sensor and not sensor.simulated:
            frame._status_lbl.config(text="\u25cf LIVE", fg=THEME["success"])
            frame._wiring_lbl.config(fg=THEME["card_bg"])  # hide wiring
        else:
            frame._status_lbl.config(text="\u25cb NOT CONNECTED", fg=THEME["text_dim"])
            frame._wiring_lbl.config(fg=THEME["text_dim"])  # show wiring

        # Update reliability
        if sensor:
            rel = sensor.reliability
            rel_color = THEME["success"] if rel >= 95 else (
                THEME["warning"] if rel >= 80 else THEME["error"]
            )
            frame._reliability_lbl.config(
                text=f"Reliability: {rel:.0f}%  ({sensor._total_reads} reads)",
                fg=rel_color,
            )

        # Redraw graph
        self._draw_graph(key)

    # ------------------------------------------------------------------
    # Graph drawing
    # ------------------------------------------------------------------

    def _draw_graph(self, key):
        frame = self._tab_frames.get(key)
        if not frame or key in ("info", "system"):
            return

        canvas = frame._canvas
        canvas.delete("all")

        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 60 or h < 60:
            return

        cfg = SENSORS[key]
        margin = {"l": 40, "r": 12, "t": 12, "b": 22}
        pw = w - margin["l"] - margin["r"]
        ph = h - margin["t"] - margin["b"]
        if pw <= 0 or ph <= 0:
            return

        # Subtle grid lines
        for i in range(1, 4):
            y = margin["t"] + i * (ph / 4)
            canvas.create_line(
                margin["l"], y, w - margin["r"], y,
                fill="#1a2332", dash=(2, 6),
            )

        for field_key, field_cfg in cfg["fields"].items():
            history = self.histories[key].get(field_key, deque())
            if len(history) < 2:
                continue

            data = list(history)
            color = field_cfg["color"]
            mode = field_cfg.get("graph_mode", "line")

            # Y-axis range
            if mode == "step":
                y_min, y_max = -0.1, 1.1
            else:
                d_min, d_max = min(data), max(data)
                d_range = d_max - d_min if d_max != d_min else 1
                y_min = d_min - d_range * 0.1
                y_max = d_max + d_range * 0.1

            # Y-axis labels
            canvas.create_text(
                margin["l"] - 4, margin["t"],
                text=f"{y_max:.0f}", anchor="e",
                fill=THEME["text_dim"], font=("Arial", 8),
            )
            canvas.create_text(
                margin["l"] - 4, h - margin["b"],
                text=f"{y_min:.0f}", anchor="e",
                fill=THEME["text_dim"], font=("Arial", 8),
            )

            # Map data to pixel coordinates
            points = []
            n = len(data)
            for i, val in enumerate(data):
                x = margin["l"] + (i / (n - 1)) * pw
                y = margin["t"] + (1.0 - (val - y_min) / (y_max - y_min)) * ph
                points.append((x, y))

            # Draw fill gradient under line traces
            if mode == "line" and len(points) >= 2:
                # Create semi-transparent fill polygon
                fill_points = list(points)
                fill_points.append((points[-1][0], h - margin["b"]))
                fill_points.append((points[0][0], h - margin["b"]))
                flat = []
                for px, py in fill_points:
                    flat.extend([px, py])
                # Use a dimmed version of the color for fill
                try:
                    r_val = int(color[1:3], 16)
                    g_val = int(color[3:5], 16)
                    b_val = int(color[5:7], 16)
                    fill_color = f"#{r_val//4:02x}{g_val//4:02x}{b_val//4:02x}"
                except (ValueError, IndexError):
                    fill_color = "#111111"
                canvas.create_polygon(
                    flat, fill=fill_color, outline="",
                )

            # Draw the trace
            if mode == "step":
                for i in range(len(points) - 1):
                    x0, y0 = points[i]
                    x1, y1 = points[i + 1]
                    canvas.create_line(x0, y0, x1, y0, fill=color, width=2)
                    canvas.create_line(x1, y0, x1, y1, fill=color, width=2)
            else:
                for i in range(len(points) - 1):
                    canvas.create_line(
                        points[i][0], points[i][1],
                        points[i + 1][0], points[i + 1][1],
                        fill=color, width=2,
                    )

            # Current value dot
            if points:
                lx, ly = points[-1]
                canvas.create_oval(lx - 4, ly - 4, lx + 4, ly + 4,
                                   fill=color, outline="")

        # Axes
        canvas.create_line(
            margin["l"], margin["t"], margin["l"], h - margin["b"],
            fill=THEME["text_dim"],
        )
        canvas.create_line(
            margin["l"], h - margin["b"], w - margin["r"], h - margin["b"],
            fill=THEME["text_dim"],
        )

        # X-axis label
        first_hist = list(self.histories[key].values())
        sample_count = len(first_hist[0]) if first_hist else 0
        canvas.create_text(
            w / 2, h - 4, text=f"{sample_count} samples",
            fill=THEME["text_dim"], font=("Arial", 8),
        )

    # ------------------------------------------------------------------
    # Logging (batched to reduce SD card writes)
    # ------------------------------------------------------------------

    def _toggle_logging(self):
        if not self.logging_active:
            os.makedirs(LOG_DIR, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file = os.path.join(LOG_DIR, f"sensor_log_{ts}.csv")

            with open(self.log_file, "w", newline="") as f:
                csv.writer(f).writerow(["timestamp", "sensor", "field", "value"])

            self.logging_active = True
            self._log_btn.config(bg=THEME["error"], text="STOP")
            self._status_lbl.config(text=f"Logging \u2192 {self.log_file}")
        else:
            self._flush_log_buffer()  # flush remaining
            self.logging_active = False
            self._log_btn.config(bg=THEME["accent"], text="LOG")
            self._status_lbl.config(text="Logging stopped")

    def _buffer_readings(self, key, readings):
        """Buffer readings for batched CSV writing."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        for field, value in readings.items():
            self.log_buffer.append([ts, key, field, value])

    def _flush_log_buffer(self):
        """Write buffered readings to CSV file."""
        if not self.log_file or not self.log_buffer:
            return
        try:
            with open(self.log_file, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(self.log_buffer)
            self.log_buffer.clear()
        except Exception as exc:
            logger.error("Log flush failed: %s", exc)

    def _schedule_log_flush(self):
        """Periodically flush the log buffer."""
        if self.logging_active:
            self._flush_log_buffer()
        self.root.after(self.log_flush_interval, self._schedule_log_flush)

    # ------------------------------------------------------------------
    # Demo mode
    # ------------------------------------------------------------------

    def _toggle_demo(self):
        self.demo_mode = not self.demo_mode
        if self.demo_mode:
            self._demo_btn.config(bg=THEME["warning"], fg="#000")
            self._status_lbl.config(text="DEMO mode  \u2502  showing simulated data")
        else:
            self._demo_btn.config(bg=THEME["accent"], fg="white")
            self._status_lbl.config(text="Demo off  \u2502  reading live sensors")

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _update_counter(self):
        """Update reading counter label on a slow timer."""
        # Count live sensors
        live = sum(1 for s in self.sensors.values() if not s.simulated)
        total = len(self.sensors)
        self._count_lbl.config(
            text=f"Sensors: {live}/{total}  \u2502  Readings: {self.reading_count}"
        )
        self.root.after(1000, self._update_counter)

    def _clear_history(self, key):
        for field in self.histories.get(key, {}):
            self.histories[key][field].clear()
        self._draw_graph(key)

    def _toggle_fullscreen(self, event=None):
        current = self.root.attributes("-fullscreen")
        self.root.attributes("-fullscreen", not current)

    def cleanup(self):
        """Release all sensor hardware resources."""
        self._flush_log_buffer()
        for sensor in self.sensors.values():
            sensor.close()
        if self._oled:
            self._oled.close()
