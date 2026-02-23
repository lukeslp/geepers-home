"""News headlines data source using NYT RSS feed.

Fetches top headlines from the NYT RSS feed (no API key needed)
and publishes them to the event bus for the news ticker.

Config example (in dashboard.yaml):
    sources:
      - id: "news.headlines"
        type: "news"
        section: "home"
        max_headlines: 8
        interval: 900
"""

import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from urllib import request, error

from core.data_source import DataSource
from core.registry import register_source

logger = logging.getLogger(__name__)

# NYT RSS feed URLs by section
RSS_FEEDS = {
    "home": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "world": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "us": "https://rss.nytimes.com/services/xml/rss/nyt/US.xml",
    "politics": "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
    "business": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "technology": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "science": "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
    "health": "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml",
    "sports": "https://rss.nytimes.com/services/xml/rss/nyt/Sports.xml",
    "arts": "https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml",
    "books": "https://rss.nytimes.com/services/xml/rss/nyt/Books.xml",
    "movies": "https://rss.nytimes.com/services/xml/rss/nyt/Movies.xml",
    "travel": "https://rss.nytimes.com/services/xml/rss/nyt/Travel.xml",
    "opinion": "https://rss.nytimes.com/services/xml/rss/nyt/Opinion.xml",
}


@register_source("news")
class NewsSource(DataSource):
    """Fetches top news headlines from NYT RSS feed."""

    def __init__(self, source_id: str, bus, config: Dict):
        config.setdefault("interval", 900)  # 15 minutes
        super().__init__(source_id, bus, config)
        self.section = config.get("section", "home")
        self.max_headlines = config.get("max_headlines", 8)
        self._timeout = config.get("timeout", 15)

        if self.section not in RSS_FEEDS:
            logger.warning("Unknown section '%s', using 'home'", self.section)
            self.section = "home"

    def fetch(self) -> Optional[Dict[str, Any]]:
        url = RSS_FEEDS.get(self.section, RSS_FEEDS["home"])

        try:
            req = request.Request(url, method="GET")
            req.add_header("User-Agent", "GeepersStation/1.0")
            with request.urlopen(req, timeout=self._timeout) as resp:
                xml_data = resp.read()

            root = ET.fromstring(xml_data)
            channel = root.find("channel")
            if channel is None:
                logger.warning("NewsSource %s: no <channel> in RSS", self.source_id)
                return None

            headlines: List[Dict[str, str]] = []
            dc_ns = "http://purl.org/dc/elements/1.1/"

            for item in channel.findall("item")[:self.max_headlines]:
                title = (item.findtext("title") or "").strip()
                if not title:
                    continue

                # Extract first category as section label
                cat_el = item.find("category")
                section = cat_el.text.strip() if cat_el is not None and cat_el.text else self.section

                headlines.append({
                    "title": title,
                    "abstract": (item.findtext("description") or "").strip(),
                    "section": section,
                    "url": (item.findtext("link") or "").strip(),
                })

            return {
                "headlines": headlines,
                "count": len(headlines),
                "section": self.section,
            }

        except error.URLError as exc:
            logger.warning("NewsSource %s: %s", self.source_id, exc)
            return None
        except ET.ParseError as exc:
            logger.warning("NewsSource %s: RSS parse error: %s", self.source_id, exc)
            return None
        except Exception as exc:
            logger.warning("NewsSource %s: %s", self.source_id, exc)
            return None
