from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass

from astrbot.api import logger


@dataclass
class RecognitionResult:
    is_loot: bool
    item_name: str
    drop_type: str
    confidence: str


RECOGNITION_PROMPT = """你是一个游戏出货截图识别助手。请分析这张图片，判断是否为游戏出货/掉落截图。

重点关注：
- 黄色字体的文字通常是稀有物品名称
- 物品名称、掉落提示等关键信息

请以 JSON 格式回复，不要包含任何其他文字：
{"is_loot": true/false, "item_name": "物品名称", "drop_type": "equipment/material/scroll/crystal/other", "confidence": "high/medium/low"}

如果不是出货截图，返回：
{"is_loot": false, "item_name": "", "drop_type": "unknown", "confidence": "low"}

drop_type 分类说明：
- equipment: 装备类（武器、防具、饰品）
- material: 材料类（矿石、木材、布料）
- scroll: 卷轴类（附魔卷轴、强化卷轴）
- crystal: 结晶/宝石类
- other: 其他类"""


JSON_PATTERN = re.compile(r'\{[^}]+\}')


class Recognizer:
    def __init__(self, context, config):
        self.context = context
        self.config = config

    async def recognize(self, image_path: str) -> RecognitionResult | None:
        provider_id = self.config.get("llm_provider_id", "gemini_flash")
        max_retries = self.config.get("max_retries", 2)

        for attempt in range(max_retries + 1):
            try:
                response = await self.context.llm_generate(
                    chat_provider_id=provider_id,
                    prompt=RECOGNITION_PROMPT,
                    image_urls=[image_path],
                )
                result_text = response.completion_text.strip()
                logger.info(f"[drop-logger] LLM response (attempt {attempt + 1}): {result_text}")

                parsed = self._parse_response(result_text)
                if parsed is not None:
                    return parsed

            except Exception as e:
                logger.error(f"[drop-logger] LLM call failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2)

        return None

    def _parse_response(self, text: str) -> RecognitionResult | None:
        # Try direct JSON parse first
        try:
            return self._build_result(json.loads(text))
        except json.JSONDecodeError:
            pass

        # Fallback: extract JSON via regex
        match = JSON_PATTERN.search(text)
        if match:
            try:
                return self._build_result(json.loads(match.group()))
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def _build_result(data: dict) -> RecognitionResult:
        return RecognitionResult(
            is_loot=data.get("is_loot", False),
            item_name=data.get("item_name", ""),
            drop_type=data.get("drop_type", "unknown"),
            confidence=data.get("confidence", "low"),
        )
