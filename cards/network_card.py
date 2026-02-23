"""Network health card -- displays Pi network status.

Shows IP address, ping latency to VPS, WiFi signal strength,
and throughput stats. Subscribes to a NetworkSource.

Config in dashboard.yaml:
    cards:
      - type: "network"
        source_id: "net.health"
        label: "Network"
        color: "#42a5f5"
        metric: "ping"    # ping, wifi, throughput, or ip
"""

import tkinter as tk
from typing import Dict

from core.base_card import BaseCard
from core.registry import register_card
from config import THEME


@register_card("network")
class NetworkCard(BaseCard):
    """Network health metric display."""

    def __init__(self, parent, bus, config: Dict):
        self._metric = config.get("metric", "ping")
        config.setdefault("bg", THEME["card_bg"])
        config.setdefault("label", "Network")
        super().__init__(parent, bus, config)

    def setup_ui(self):
        bg = self.card_config.get("bg", THEME["card_bg"])
        color = self.card_config.get("color", "#42a5f5")

        # Top: icon + label
        top = tk.Frame(self, bg=bg)
        top.pack(fill="x", padx=12, pady=(10, 0))

        self._icon_lbl = tk.Label(
            top, text="\u26a1", font=("Arial", 10), bg=bg, fg=THEME["text_dim"],
        )
        self._icon_lbl.pack(side="left")

        tk.Label(
            top,
            text=self.card_config.get("label", "Network"),
            font=("Arial", 11),
            bg=bg,
            fg=THEME["text_dim"],
        ).pack(side="left", padx=(4, 0))

        # Primary metric
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

        # Secondary stats
        bot = tk.Frame(self, bg=bg)
        bot.pack(fill="x", padx=12, pady=(0, 10))

        self._stat1 = tk.Label(
            bot, text="", font=("Arial", 9), bg=bg, fg=THEME["text_dim"],
        )
        self._stat1.pack(side="left")

        self._stat2 = tk.Label(
            bot, text="", font=("Arial", 9), bg=bg, fg=THEME["text_dim"],
        )
        self._stat2.pack(side="right")

    def on_data(self, payload: Dict):
        metric = self._metric

        if metric == "ping":
            ping = payload.get("ping_ms", -1)
            if ping < 0:
                self._value_lbl.config(text="--", fg="#ff5252")
                self._sub_lbl.config(text="No response")
            else:
                color = self._ping_color(ping)
                self._value_lbl.config(text=f"{ping:.0f}", fg=color)
                self._sub_lbl.config(text="ms latency")
            ip = payload.get("ip", "?")
            self._stat1.config(text=f"IP {ip}")
            conns = payload.get("connections", 0)
            self._stat2.config(text=f"{conns} conn")

        elif metric == "wifi":
            pct = payload.get("wifi_pct", -1)
            if pct < 0:
                self._value_lbl.config(text="N/A", fg=THEME["text_dim"])
                self._sub_lbl.config(text="No WiFi")
            else:
                color = self._signal_color(pct)
                self._value_lbl.config(text=f"{pct:.0f}%", fg=color)
                self._sub_lbl.config(text="signal strength")
            sig = payload.get("wifi_signal", 0)
            self._stat1.config(text=f"{sig:.0f} dBm" if sig else "")
            iface = payload.get("wifi_interface", "")
            self._stat2.config(text=iface)

        elif metric == "throughput":
            rx = payload.get("rx_kbps", 0)
            tx = payload.get("tx_kbps", 0)
            # Show the larger of rx/tx as the primary
            primary = max(rx, tx)
            if primary > 1024:
                self._value_lbl.config(
                    text=f"{primary / 1024:.1f}", fg="#42a5f5",
                )
                self._sub_lbl.config(text="MB/s")
            else:
                self._value_lbl.config(
                    text=f"{primary:.0f}", fg="#42a5f5",
                )
                self._sub_lbl.config(text="KB/s")
            self._stat1.config(text=f"\u2193 {rx:.0f} KB/s")
            self._stat2.config(text=f"\u2191 {tx:.0f} KB/s")

        elif metric == "ip":
            ip = payload.get("ip", "?")
            hostname = payload.get("hostname", "?")
            # Show IP as the main value, smaller font
            self._value_lbl.config(
                text=ip, font=("Arial", 18, "bold"), fg="#42a5f5",
            )
            self._sub_lbl.config(text=hostname)
            ping = payload.get("ping_ms", -1)
            self._stat1.config(
                text=f"Ping {ping:.0f}ms" if ping >= 0 else "Ping --",
            )
            conns = payload.get("connections", 0)
            self._stat2.config(text=f"{conns} conn")

    @staticmethod
    def _ping_color(ms):
        if ms < 30:
            return "#00d084"
        elif ms < 100:
            return "#42a5f5"
        elif ms < 300:
            return "#ffa726"
        return "#ff5252"

    @staticmethod
    def _signal_color(pct):
        if pct > 70:
            return "#00d084"
        elif pct > 40:
            return "#ffa726"
        return "#ff5252"
