"""Weather card -- displays current conditions from Open-Meteo API.

Subscribes to a RESTSource fetching Open-Meteo's current_weather endpoint.
Interprets WMO weather codes into readable conditions and Unicode icons.
Shows temperature, conditions, wind speed, and wind direction.

Config in dashboard.yaml:
    cards:
      - type: "weather"
        source_id: "api.weather"
        label: "Weather"
        color: "#42a5f5"
        temp_unit: "C"          # C or F
"""

import tkinter as tk
from typing import Dict

from core.base_card import BaseCard
from core.registry import register_card
from config import THEME

# WMO Weather interpretation codes
# https://open-meteo.com/en/docs (WMO code table)
WMO_CODES = {
    0: ("\u2600", "Clear"),            # sun
    1: ("\u26c5", "Mostly Clear"),     # sun behind cloud
    2: ("\u26c5", "Partly Cloudy"),
    3: ("\u2601", "Overcast"),         # cloud
    45: ("\u2601", "Fog"),
    48: ("\u2601", "Rime Fog"),
    51: ("\u2602", "Light Drizzle"),   # umbrella
    53: ("\u2602", "Drizzle"),
    55: ("\u2602", "Heavy Drizzle"),
    56: ("\u2744", "Freezing Drizzle"),
    57: ("\u2744", "Heavy Frz Drizzle"),
    61: ("\u2614", "Light Rain"),      # umbrella with drops
    63: ("\u2614", "Rain"),
    65: ("\u2614", "Heavy Rain"),
    66: ("\u2744", "Freezing Rain"),
    67: ("\u2744", "Heavy Frz Rain"),
    71: ("\u2744", "Light Snow"),      # snowflake
    73: ("\u2744", "Snow"),
    75: ("\u2744", "Heavy Snow"),
    77: ("\u2744", "Snow Grains"),
    80: ("\u2614", "Light Showers"),
    81: ("\u2614", "Showers"),
    82: ("\u2614", "Heavy Showers"),
    85: ("\u2744", "Light Snow Shw"),
    86: ("\u2744", "Heavy Snow Shw"),
    95: ("\u26a1", "Thunderstorm"),    # lightning
    96: ("\u26a1", "T-storm + Hail"),
    99: ("\u26a1", "T-storm + Hvy Hail"),
}

# Wind direction from degrees
WIND_DIRS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
             "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def wind_direction(degrees):
    """Convert wind direction degrees to compass label."""
    idx = round(degrees / 22.5) % 16
    return WIND_DIRS[idx]


@register_card("weather")
class WeatherCard(BaseCard):
    """Current weather conditions from Open-Meteo."""

    def __init__(self, parent, bus, config: Dict):
        self._temp_unit = config.get("temp_unit", "C")
        config.setdefault("bg", THEME["card_bg"])
        config.setdefault("label", "Weather")
        super().__init__(parent, bus, config)

    def setup_ui(self):
        bg = self.card_config.get("bg", THEME["card_bg"])
        color = self.card_config.get("color", "#42a5f5")

        # Top: icon + label
        top = tk.Frame(self, bg=bg)
        top.pack(fill="x", padx=12, pady=(10, 0))

        self._icon_lbl = tk.Label(
            top, text="\u2600", font=("Arial", 12), bg=bg, fg=color,
        )
        self._icon_lbl.pack(side="left")

        tk.Label(
            top,
            text=self.card_config.get("label", "Weather"),
            font=("Arial", 11),
            bg=bg,
            fg=THEME["text_dim"],
        ).pack(side="left", padx=(4, 0))

        # Primary: temperature
        mid = tk.Frame(self, bg=bg)
        mid.pack(fill="both", expand=True, padx=12)

        self._temp_lbl = tk.Label(
            mid, text="--", font=("Arial", 32, "bold"), bg=bg, fg=color,
        )
        self._temp_lbl.pack(anchor="center", pady=(4, 0))

        self._cond_lbl = tk.Label(
            mid, text="Loading...", font=("Arial", 10), bg=bg, fg=THEME["text_dim"],
        )
        self._cond_lbl.pack(anchor="center")

        # Secondary: wind
        bot = tk.Frame(self, bg=bg)
        bot.pack(fill="x", padx=12, pady=(0, 10))

        self._wind_lbl = tk.Label(
            bot, text="", font=("Arial", 9), bg=bg, fg=THEME["text_dim"],
        )
        self._wind_lbl.pack(side="left")

        self._dir_lbl = tk.Label(
            bot, text="", font=("Arial", 9), bg=bg, fg=THEME["text_dim"],
        )
        self._dir_lbl.pack(side="right")

    def on_data(self, payload: Dict):
        temp = payload.get("temperature")
        code = payload.get("weathercode", payload.get("weather_code", -1))
        wind = payload.get("windspeed", payload.get("wind_speed_10m"))
        wind_dir = payload.get("winddirection", payload.get("wind_direction_10m"))

        # Temperature
        if temp is not None:
            unit = "\u00b0F" if self._temp_unit == "F" else "\u00b0C"
            color = self._temp_color(temp)
            self._temp_lbl.config(text=f"{temp:.1f}{unit}", fg=color)

        # Weather condition
        icon, desc = WMO_CODES.get(code, ("\u2753", "Unknown"))
        self._icon_lbl.config(text=icon)
        self._cond_lbl.config(text=desc)

        # Wind
        if wind is not None:
            self._wind_lbl.config(text=f"Wind {wind:.0f} km/h")
        if wind_dir is not None:
            self._dir_lbl.config(text=wind_direction(wind_dir))

    @staticmethod
    def _temp_color(temp):
        """Color-code temperature."""
        if temp < 5:
            return "#40a0ff"   # cold blue
        elif temp < 15:
            return "#42a5f5"   # cool blue
        elif temp < 22:
            return "#00d084"   # comfortable green
        elif temp < 30:
            return "#ffa726"   # warm orange
        return "#ff5252"       # hot red
