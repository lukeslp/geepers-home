"""Dedicated weather data source using Open-Meteo API.

Fetches current conditions, hourly forecast, and sunrise/sunset data.
Publishes structured weather data to the event bus for the enhanced
weather card with indoor/outdoor comparison.

Config example (in dashboard.yaml):
    sources:
      - id: "api.weather"
        type: "weather"
        latitude: 34.4275
        longitude: -119.859
        interval: 600
"""

import json
import logging
from typing import Any, Dict, Optional
from urllib import request, error

from core.data_source import DataSource
from core.registry import register_source

logger = logging.getLogger(__name__)

# WMO Weather interpretation codes → description + icon
# https://open-meteo.com/en/docs#weathervariables
WMO_CODES = {
    0: ("Clear sky", "clear"),
    1: ("Mainly clear", "clear"),
    2: ("Partly cloudy", "partly_cloudy"),
    3: ("Overcast", "cloudy"),
    45: ("Fog", "fog"),
    48: ("Depositing rime fog", "fog"),
    51: ("Light drizzle", "drizzle"),
    53: ("Moderate drizzle", "drizzle"),
    55: ("Dense drizzle", "drizzle"),
    56: ("Light freezing drizzle", "drizzle"),
    57: ("Dense freezing drizzle", "drizzle"),
    61: ("Slight rain", "rain"),
    63: ("Moderate rain", "rain"),
    65: ("Heavy rain", "rain"),
    66: ("Light freezing rain", "rain"),
    67: ("Heavy freezing rain", "rain"),
    71: ("Slight snow", "snow"),
    73: ("Moderate snow", "snow"),
    75: ("Heavy snow", "snow"),
    77: ("Snow grains", "snow"),
    80: ("Slight showers", "showers"),
    81: ("Moderate showers", "showers"),
    82: ("Violent showers", "showers"),
    85: ("Slight snow showers", "snow"),
    86: ("Heavy snow showers", "snow"),
    95: ("Thunderstorm", "thunderstorm"),
    96: ("Thunderstorm with slight hail", "thunderstorm"),
    99: ("Thunderstorm with heavy hail", "thunderstorm"),
}


@register_source("weather")
class WeatherSource(DataSource):
    """Fetches current weather + daily sun data from Open-Meteo."""

    def __init__(self, source_id: str, bus, config: Dict):
        config.setdefault("interval", 600)  # 10 minutes
        super().__init__(source_id, bus, config)
        self.latitude = config.get("latitude", 34.4275)
        self.longitude = config.get("longitude", -119.859)
        self._timeout = config.get("timeout", 15)

    def fetch(self) -> Optional[Dict[str, Any]]:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={self.latitude}&longitude={self.longitude}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
            f"weather_code,wind_speed_10m,pressure_msl,is_day"
            f"&daily=sunrise,sunset,uv_index_max"
            f"&timezone=auto&forecast_days=1"
        )

        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self._timeout) as resp:
                raw = json.loads(resp.read())

            current = raw.get("current", {})
            daily = raw.get("daily", {})

            weather_code = current.get("weather_code", 0)
            desc, icon = WMO_CODES.get(weather_code, ("Unknown", "clear"))
            is_day = current.get("is_day", 1)

            result = {
                # Outdoor conditions (prefixed to avoid collision with indoor sensors)
                "outdoor_temp": current.get("temperature_2m"),
                "outdoor_humidity": current.get("relative_humidity_2m"),
                "feels_like": current.get("apparent_temperature"),
                "outdoor_pressure": current.get("pressure_msl"),
                "wind_speed": current.get("wind_speed_10m"),
                "weather_code": weather_code,
                "weather_desc": desc,
                "weather_icon": icon,
                "is_day": is_day,
            }

            # Sunrise/sunset (first element of daily arrays)
            sunrises = daily.get("sunrise", [])
            sunsets = daily.get("sunset", [])
            uv_maxes = daily.get("uv_index_max", [])

            if sunrises:
                result["sunrise"] = sunrises[0]
            if sunsets:
                result["sunset"] = sunsets[0]
            if uv_maxes:
                result["uv_max"] = uv_maxes[0]

            return result

        except error.URLError as exc:
            logger.warning("WeatherSource %s: %s", self.source_id, exc)
            return None
        except Exception as exc:
            logger.warning("WeatherSource %s: %s", self.source_id, exc)
            return None
