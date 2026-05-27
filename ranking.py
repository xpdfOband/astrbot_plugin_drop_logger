from __future__ import annotations

from .db import DropDB, RankingEntry

MEDAL = ["🥇", "🥈", "🥉"]


class Ranking:
    def __init__(self, db: DropDB, config: dict):
        self.db = db
        self.config = config

    async def get_ranking(self, group_id: str, days: int | None = None) -> list[RankingEntry]:
        if days is None:
            days = self.config.get("ranking_days", 7)
        return await self.db.get_ranking(group_id, days)

    def format_text(self, entries: list[RankingEntry], days: int) -> str:
        if not entries:
            return f"出货排行榜（最近{days}天）\n暂无出货记录，快去搬砖吧！"

        lines = [f"出货排行榜（最近{days}天）", "━━━━━━━━━━━━━━━"]
        for i, entry in enumerate(entries):
            medal = MEDAL[i] if i < len(MEDAL) else f"{i + 1}."
            items_short = entry.items[:30] + "..." if len(entry.items) > 30 else entry.items
            lines.append(f"{medal} {entry.user_name}  {entry.drop_count}次  {items_short}")

        return "\n".join(lines)
