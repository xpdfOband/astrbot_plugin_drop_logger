from __future__ import annotations

import re
from typing import Pattern

from astrbot.api import logger

from .db import DropDB, DropRecord
from .recognizer import RecognitionResult


class Recorder:
    def __init__(self, db: DropDB, config):
        self.db = db
        self.config = config
        self._trigger_patterns = self._compile_patterns(
            config.get("trigger_keywords", [])
        )
        self._exclude_patterns = self._compile_patterns(
            config.get("exclude_keywords", [])
        )

    @staticmethod
    def _compile_patterns(keywords: list[str]) -> list[tuple[str, Pattern | None]]:
        """Precompile regex patterns from keyword list."""
        result = []
        for kw in keywords:
            if kw.startswith("/") and kw.endswith("/") and len(kw) > 2:
                result.append((kw, re.compile(kw[1:-1])))
            else:
                result.append((kw, None))
        return result

    def _matches_keyword(self, item_name: str) -> bool:
        for kw, pattern in self._exclude_patterns:
            if self._keyword_match(item_name, kw, pattern):
                return False

        for kw, pattern in self._trigger_patterns:
            if self._keyword_match(item_name, kw, pattern):
                return True

        return False

    # 常见口语前缀，提取物品名时去掉
    _PREFIX_PATTERN = re.compile(
        r"^(我|俺|咱)?(出了?|出了?个|出了?件|掉了?|获得[了]?|爆了?|摸到?了?)\s*",
        re.IGNORECASE,
    )

    def _extract_item_name(self, text: str) -> str:
        """从口语化文本中提取物品名。如 '我出了一个 高雅附魔卷轴' -> '高雅附魔卷轴'"""
        cleaned = self._PREFIX_PATTERN.sub("", text.strip())
        return cleaned.strip()

    @staticmethod
    def _keyword_match(text: str, keyword: str, compiled: Pattern | None = None) -> bool:
        if compiled is not None:
            return bool(compiled.search(text))
        return keyword in text

    def _build_record(self, record_id: int, group_id: str, user_id: str,
                      user_name: str, drop_name: str, drop_type: str,
                      source: str, remark: str = "", image_path: str = "") -> DropRecord:
        return DropRecord(
            id=record_id,
            group_id=group_id,
            user_id=user_id,
            user_name=user_name,
            drop_name=drop_name,
            drop_type=drop_type,
            source=source,
            gold_value=0,
            remark=remark,
            image_path=image_path,
            created_at="",
        )

    async def record_image(
        self,
        result: RecognitionResult,
        group_id: str,
        user_id: str,
        user_name: str,
        image_path: str = "",
        remark: str = "",
    ) -> DropRecord | None:
        if not result.is_loot or not result.item_name:
            return None

        if not self._matches_keyword(result.item_name):
            logger.info(f"[drop-logger] '{result.item_name}' not matched by keywords, skipping")
            return None

        record_id = await self.db.add_record(
            group_id=group_id,
            user_id=user_id,
            user_name=user_name,
            drop_name=result.item_name,
            drop_type=result.drop_type,
            source="image",
            remark=remark,
            image_path=image_path,
        )

        logger.info(f"[drop-logger] Recorded image loot: {result.item_name} by {user_name} (id={record_id})")

        return self._build_record(
            record_id, group_id, user_id, user_name,
            result.item_name, result.drop_type, "image",
            remark=remark, image_path=image_path,
        )

    async def record_text(
        self,
        text: str,
        group_id: str,
        user_id: str,
        user_name: str,
    ) -> DropRecord | None:
        drop_name = self._extract_item_name(text)
        if not drop_name:
            return None

        if not self._matches_keyword(drop_name):
            logger.info(f"[drop-logger] Text '{drop_name}' not matched by keywords, skipping")
            return None

        tag = self.config.get("text_append_tag", "出货")
        remark = f"{text.strip()} ({tag})"

        record_id = await self.db.add_record(
            group_id=group_id,
            user_id=user_id,
            user_name=user_name,
            drop_name=drop_name,
            drop_type="unknown",
            source="text",
            remark=remark,
        )

        logger.info(f"[drop-logger] Recorded text loot: {drop_name} by {user_name} (id={record_id})")

        return self._build_record(
            record_id, group_id, user_id, user_name,
            drop_name, "unknown", "text", remark=remark,
        )
