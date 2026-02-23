"""Generic REST API data source.

Fetches JSON from any HTTP endpoint at a configurable interval.
Supports optional JSONPath-like field extraction and headers.

Config example (in dashboard.yaml):
    sources:
      - id: "api.weather"
        type: "rest"
        url: "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current_weather=true"
        interval: 600
        extract: "current_weather"   # optional: pull nested key
        headers:                     # optional
          Authorization: "Bearer xxx"
"""

import json
import logging
from typing import Any, Dict, Optional
from urllib import request, error

from core.data_source import DataSource
from core.registry import register_source

logger = logging.getLogger(__name__)


@register_source("rest")
class RESTSource(DataSource):
    """Fetches JSON from a REST endpoint."""

    def __init__(self, source_id: str, bus, config: Dict):
        config.setdefault("interval", 60.0)
        super().__init__(source_id, bus, config)
        self.url = config.get("url", "")
        self.headers = config.get("headers", {})
        self.extract_key = config.get("extract", None)
        self._timeout = config.get("timeout", 10)

    def fetch(self) -> Optional[Dict[str, Any]]:
        if not self.url:
            return None

        try:
            req = request.Request(self.url, method="GET")
            for k, v in self.headers.items():
                req.add_header(k, v)

            with request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read())

            # Extract nested key if specified
            if self.extract_key:
                for key in self.extract_key.split("."):
                    if isinstance(data, dict):
                        data = data.get(key, {})

            # Ensure we return a dict
            if not isinstance(data, dict):
                data = {"value": data}

            return data

        except error.URLError as exc:
            logger.warning("RESTSource %s: %s", self.source_id, exc)
            return None
        except Exception as exc:
            logger.warning("RESTSource %s: %s", self.source_id, exc)
            return None
