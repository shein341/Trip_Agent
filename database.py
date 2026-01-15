"""
旅行历史记录数据库模块
使用 SQLite + aiosqlite 异步操作
"""
import aiosqlite
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

DATABASE_PATH = "travel_history.db"


class TravelRecord(BaseModel):
    """旅行记录模型"""
    id: int
    departure: str = ""  # 出发地（默认空以兼容旧数据）
    destination: str
    budget: int
    start_date: str
    end_date: str
    plan_content: str
    created_at: str


async def init_db():
    """初始化数据库表"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # 创建新表（如果不存在）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS travel_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                departure TEXT DEFAULT '',
                destination TEXT NOT NULL,
                budget INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                plan_content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # 尝试添加 departure 列（如果表已存在但缺少此列）
        try:
            await db.execute("ALTER TABLE travel_history ADD COLUMN departure TEXT DEFAULT ''")
        except:
            pass  # 列已存在
            
        await db.commit()


async def save_plan(
    destination: str,
    budget: int,
    start_date: str,
    end_date: str,
    plan_content: str,
    departure: str = ""
) -> int:
    """保存旅行规划到数据库"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO travel_history 
            (departure, destination, budget, start_date, end_date, plan_content, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (departure, destination, budget, start_date, end_date, plan_content, 
             datetime.now().isoformat())
        )
        await db.commit()
        return cursor.lastrowid


async def get_history(limit: int = 20) -> List[TravelRecord]:
    """获取历史记录列表"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, COALESCE(departure, '') as departure, destination, 
                   budget, start_date, end_date, plan_content, created_at
            FROM travel_history 
            ORDER BY created_at DESC 
            LIMIT ?
            """,
            (limit,)
        )
        rows = await cursor.fetchall()
        return [TravelRecord(**dict(row)) for row in rows]


async def get_plan_by_id(plan_id: int) -> Optional[TravelRecord]:
    """根据 ID 获取单个规划"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, COALESCE(departure, '') as departure, destination,
                   budget, start_date, end_date, plan_content, created_at
            FROM travel_history WHERE id = ?
            """,
            (plan_id,)
        )
        row = await cursor.fetchone()
        if row:
            return TravelRecord(**dict(row))
        return None


async def delete_plan(plan_id: int) -> bool:
    """删除旅行规划"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM travel_history WHERE id = ?",
            (plan_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
