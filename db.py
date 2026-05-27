from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta

import aiosqlite

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS drop_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_name TEXT NOT NULL,
    drop_name TEXT NOT NULL,
    drop_type TEXT DEFAULT 'unknown',
    source TEXT DEFAULT 'image',
    gold_value REAL DEFAULT 0,
    remark TEXT DEFAULT '',
    image_path TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_group_user ON drop_records(group_id, user_id);",
    "CREATE INDEX IF NOT EXISTS idx_created ON drop_records(created_at);",
]


@dataclass
class DropRecord:
    id: int
    group_id: str
    user_id: str
    user_name: str
    drop_name: str
    drop_type: str
    source: str
    gold_value: float
    remark: str
    image_path: str
    created_at: str


@dataclass
class RankingEntry:
    user_id: str
    user_name: str
    drop_count: int
    items: str
    total_value: float
    last_drop_time: str


class DropDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.execute(CREATE_TABLE_SQL)
        for idx_sql in CREATE_INDEX_SQL:
            await self._conn.execute(idx_sql)
        await self._conn.commit()

    async def terminate(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def add_record(
        self,
        group_id: str,
        user_id: str,
        user_name: str,
        drop_name: str,
        drop_type: str = "unknown",
        source: str = "image",
        gold_value: float = 0,
        remark: str = "",
        image_path: str = "",
    ) -> int:
        cursor = await self._conn.execute(
            """INSERT INTO drop_records
               (group_id, user_id, user_name, drop_name, drop_type, source, gold_value, remark, image_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (group_id, user_id, user_name, drop_name, drop_type, source, gold_value, remark, image_path),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_ranking(self, group_id: str, days: int = 7) -> list[RankingEntry]:
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        self._conn.row_factory = aiosqlite.Row
        cursor = await self._conn.execute(
            """SELECT user_id, user_name,
                      COUNT(*) as drop_count,
                      GROUP_CONCAT(DISTINCT drop_name) as items,
                      SUM(gold_value) as total_value,
                      MAX(created_at) as last_drop_time
               FROM drop_records
               WHERE group_id = ? AND created_at >= ?
               GROUP BY user_id
               ORDER BY drop_count DESC, last_drop_time DESC
               LIMIT 20""",
            (group_id, since),
        )
        rows = await cursor.fetchall()
        self._conn.row_factory = None
        return [RankingEntry(**dict(row)) for row in rows]

    async def get_user_weekly_count(self, user_id: str, group_id: str) -> int:
        since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        cursor = await self._conn.execute(
            """SELECT COUNT(*) FROM drop_records
               WHERE user_id = ? AND group_id = ? AND created_at >= ?""",
            (user_id, group_id, since),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
