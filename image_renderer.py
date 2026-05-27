from __future__ import annotations

import os
from datetime import datetime

from astrbot.api import logger
from jinja2 import Template

from .db import RankingEntry
from .ranking import MEDAL

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "ranking.html")


class ImageRenderer:
    def __init__(self, star_instance):
        self.star = star_instance
        template_str = self._load_template()
        self._template = Template(template_str) if template_str else None

    def _load_template(self) -> str | None:
        try:
            with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"[drop-logger] Template not found: {TEMPLATE_PATH}")
            return None
        except Exception as e:
            logger.error(f"[drop-logger] Failed to load template: {e}")
            return None

    async def render_ranking(self, entries: list[RankingEntry], days: int) -> str | None:
        if not entries or not self._template:
            return None

        html_content = self._template.render(
            entries=entries,
            days=days,
            medals=MEDAL,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

        try:
            image_path = await self.star.html_render(
                html_content,
                return_url=True,
            )
            logger.info(f"[drop-logger] Ranking image rendered: {image_path}")
            return image_path
        except Exception as e:
            logger.error(f"[drop-logger] Image render failed: {e}")
            return None
