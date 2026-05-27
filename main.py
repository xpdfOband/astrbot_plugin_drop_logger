from __future__ import annotations

import os

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Image, Plain
from astrbot.api.star import Context, Star, StarTools
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.platform.message_session import MessageSession

from .db import DropDB
from .image_renderer import ImageRenderer
from .notifier import Notifier
from .ranking import Ranking
from .recorder import Recorder
from .recognizer import Recognizer

DATA_DIR = StarTools.get_data_dir("astrbot_plugin_drop_logger")


class DropLoggerPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context, config)
        db_path = os.path.join(DATA_DIR, "drops.db")
        self.db = DropDB(db_path)
        self.recognizer = Recognizer(context, self.config)
        self.recorder = Recorder(self.db, self.config)
        self.ranking = Ranking(self.db, self.config)
        self.notifier = Notifier(self.db, self.config)
        self.image_renderer = ImageRenderer(self)

    async def initialize(self):
        await self.db.initialize()
        logger.info("[drop-logger] Plugin initialized")

        group_ids = self.config.get("target_group_ids", [])
        if group_ids:
            cron_expr = self.config.get("cron_expression", "0 20 * * 0")
            try:
                await self.context.cron_manager.add_basic_job(
                    name="drop_logger_weekly_ranking",
                    cron_expression=cron_expr,
                    handler=self._cron_ranking_handler,
                    description="出货排行榜定时播报",
                    persistent=True,
                )
                logger.info(f"[drop-logger] Cron job registered: {cron_expr}")
            except Exception as e:
                logger.error(f"[drop-logger] Failed to register cron job: {e}")

    async def terminate(self):
        await self.db.terminate()
        logger.info("[drop-logger] Plugin terminated")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        if not event.is_at_or_wake_command:
            return

        group_id = event.get_group_id()
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()

        messages = event.get_messages()
        images = [c for c in messages if isinstance(c, Image)]
        texts = []
        for c in messages:
            if isinstance(c, Plain):
                stripped = c.text.strip()
                if stripped and not stripped.startswith("/"):
                    texts.append(stripped)

        if not images and not texts:
            return

        remark = " ".join(texts) if images and texts else ""

        for img in images:
            try:
                file_path = await img.convert_to_file_path()
            except Exception as e:
                logger.error(f"[drop-logger] Failed to get image path: {e}")
                continue

            result = await self.recognizer.recognize(file_path)
            if result is None:
                continue

            record = await self.recorder.record_image(
                result=result,
                group_id=group_id,
                user_id=user_id,
                user_name=user_name,
                image_path=file_path,
                remark=remark,
            )

            if record and self.notifier.should_reply():
                reply = await self.notifier.format_record_reply(record)
                yield event.plain_result(reply)

        if not images and texts and self.config.get("enable_text_record", True):
            text_content = " ".join(texts)
            record = await self.recorder.record_text(
                text=text_content,
                group_id=group_id,
                user_id=user_id,
                user_name=user_name,
            )

            if record and self.notifier.should_reply():
                reply = await self.notifier.format_record_reply(record)
                yield event.plain_result(reply)

        event.stop_event()

    @filter.command("出货排行")
    async def handle_ranking(self, event: AstrMessageEvent, days: int = None):
        group_id = event.get_group_id()
        ranking_days = days or self.config.get("ranking_days", 7)

        entries = await self.ranking.get_ranking(group_id, ranking_days)
        text = self.ranking.format_text(entries, ranking_days)
        yield event.plain_result(text)

    async def _cron_ranking_handler(self):
        group_ids = self.config.get("target_group_ids", [])
        days = self.config.get("ranking_days", 7)

        for gid in group_ids:
            try:
                entries = await self.ranking.get_ranking(gid, days)
                if not entries:
                    continue

                image_path = await self.image_renderer.render_ranking(entries, days)
                if image_path:
                    chain = MessageChain(chain=[Image(file=image_path)])
                else:
                    text = self.ranking.format_text(entries, days)
                    chain = MessageChain(chain=[Plain(text)])

                session = MessageSession.from_str(f"aiocqhttp:group:{gid}")
                await self.context.send_message(session, chain)
                logger.info(f"[drop-logger] Ranking sent to group {gid}")

            except Exception as e:
                logger.error(f"[drop-logger] Cron ranking failed for group {gid}: {e}")
