from __future__ import annotations

from .db import DropDB, DropRecord


class Notifier:
    def __init__(self, db: DropDB, config: dict):
        self.db = db
        self.config = config

    async def format_record_reply(self, record: DropRecord) -> str:
        weekly_count = await self.db.get_user_weekly_count(
            record.user_id, record.group_id
        )

        if record.source == "image":
            lines = [
                "✅ 已记录出货！",
                f"  物品：{record.drop_name}",
                f"  分类：{record.drop_type}",
            ]
        else:
            lines = [
                "✅ 已记录出货！",
                f"  内容：{record.drop_name}",
            ]

        lines.append(f"  {record.user_name} 本周第 {weekly_count} 次出货")
        return "\n".join(lines)

    def should_reply(self) -> bool:
        return self.config.get("auto_reply", True)
