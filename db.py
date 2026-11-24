import logging
from datetime import datetime, date
from typing import Optional

import aiosqlite

from config import DB_PATH

log = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category_id INTEGER NULL REFERENCES categories(id) ON DELETE SET NULL,
    difficulty INTEGER NOT NULL CHECK(difficulty IN (0,1,2)),
    type TEXT NOT NULL CHECK(type IN ('oneoff','recurring')),
    deadline TEXT NULL,
    period_days INTEGER NULL,
    period_start TEXT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active','done','expired','cancelled')),
    completed_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    completed_at TEXT NULL
);
CREATE TABLE IF NOT EXISTS completions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    completed_at TEXT,
    coins INTEGER
);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


def _row_to_task(row) -> dict:
    keys = [
        "id", "title", "category_id", "difficulty", "type", "deadline",
        "period_days", "period_start", "status", "completed_count",
        "created_at", "completed_at",
    ]
    return dict(zip(keys, row))


# ---------- USERS / COINS ----------

async def ensure_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users(user_id, coins) VALUES(?,0)", (user_id,)
        )
        await db.commit()


async def get_balance(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT coins FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else 0


async def add_coins(user_id: int, delta: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users(user_id, coins) VALUES(?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET coins = coins + ?",
            (user_id, max(delta, 0) if delta > 0 else 0, delta),
        )
        await db.commit()


# ---------- CATEGORIES ----------

async def list_categories() -> list[tuple[int, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, name FROM categories ORDER BY name")
        return await cur.fetchall()


async def find_category(name: str) -> Optional[tuple[int, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, name FROM categories WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))",
            (name,),
        )
        return await cur.fetchone()


async def add_category(name: str) -> Optional[int]:
    name = name.strip()
    if not name:
        return None
    if await find_category(name):
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("INSERT INTO categories(name) VALUES(?)", (name,))
        await db.commit()
        return cur.lastrowid


async def delete_category(cat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tasks SET category_id=NULL WHERE category_id=?", (cat_id,))
        await db.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        await db.commit()


# ---------- TASKS ----------

async def find_active_by_title(title: str, exclude_id: Optional[int] = None):
    sql = (
        "SELECT id FROM tasks WHERE LOWER(TRIM(title)) = LOWER(TRIM(?)) "
        "AND status='active'"
    )
    params = [title]
    if exclude_id:
        sql += " AND id != ?"
        params.append(exclude_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(sql, params)
        return await cur.fetchall()


async def create_task(
    title: str,
    category_id: Optional[int],
    difficulty: int,
    ttype: str,
    deadline: Optional[str] = None,
    period_days: Optional[int] = None,
    period_start: Optional[str] = None,
) -> int:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO tasks(title, category_id, difficulty, type, deadline, "
            "period_days, period_start, status, created_at) "
            "VALUES(?,?,?,?,?,?,?, 'active', ?)",
            (title, category_id, difficulty, ttype, deadline, period_days,
             period_start, now),
        )
        await db.commit()
        return cur.lastrowid


async def get_task(task_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, title, category_id, difficulty, type, deadline, "
            "period_days, period_start, status, completed_count, created_at, "
            "completed_at FROM tasks WHERE id=?",
            (task_id,),
        )
        row = await cur.fetchone()
    return _row_to_task(row) if row else None


async def get_task_with_category(task_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT t.id, t.title, t.category_id, t.difficulty, t.type, "
            "t.deadline, t.period_days, t.period_start, t.status, "
            "t.completed_count, t.created_at, t.completed_at, c.name "
            "FROM tasks t LEFT JOIN categories c ON t.category_id = c.id "
            "WHERE t.id=?",
            (task_id,),
        )
        row = await cur.fetchone()
    if not row:
        return None
    d = _row_to_task(row[:12])
    d["category_name"] = row[12]
    return d


async def list_active_tasks() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT t.id, t.title, t.category_id, t.difficulty, t.type, "
            "t.deadline, t.period_days, t.period_start, t.status, "
            "t.completed_count, t.created_at, t.completed_at, c.name "
            "FROM tasks t LEFT JOIN categories c ON t.category_id = c.id "
            "WHERE t.status IN ('active','expired')"
        )
        rows = await cur.fetchall()
    out = []
    for row in rows:
        d = _row_to_task(row[:12])
        d["category_name"] = row[12]
        out.append(d)
    return out


async def update_task(task_id: int, **fields):
    if not fields:
        return
    allowed = {
        "title", "category_id", "difficulty", "deadline",
        "period_days", "period_start", "status", "completed_count",
        "completed_at",
    }
    keys = [k for k in fields if k in allowed]
    if not keys:
        return
    set_clause = ", ".join(f"{k}=?" for k in keys)
    values = [fields[k] for k in keys] + [task_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE tasks SET {set_clause} WHERE id=?", values)
        await db.commit()


async def delete_task(task_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        await db.commit()


async def mark_expired(today_iso: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tasks SET status='expired' WHERE type='oneoff' "
            "AND status='active' AND deadline IS NOT NULL AND deadline < ?",
            (today_iso,),
        )
        await db.commit()


async def search_active_by_partial(text: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT t.id, t.title, t.category_id, t.difficulty, t.type, "
            "t.deadline, t.period_days, t.period_start, t.status, "
            "t.completed_count, t.created_at, t.completed_at, c.name "
            "FROM tasks t LEFT JOIN categories c ON t.category_id = c.id "
            "WHERE t.status IN ('active','expired') "
            "AND LOWER(t.title) LIKE LOWER(?)",
            (f"%{text}%",),
        )
        rows = await cur.fetchall()
    out = []
    for row in rows:
        d = _row_to_task(row[:12])
        d["category_name"] = row[12]
        out.append(d)
    return out


# ---------- COMPLETIONS ----------

async def add_completion(task_id: int, coins: int) -> int:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO completions(task_id, completed_at, coins) VALUES(?,?,?)",
            (task_id, now, coins),
        )
        await db.commit()
        return cur.lastrowid


async def get_last_completion(task_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, task_id, completed_at, coins FROM completions "
            "WHERE task_id=? ORDER BY id DESC LIMIT 1",
            (task_id,),
        )
        row = await cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "task_id": row[1], "completed_at": row[2], "coins": row[3]}


async def delete_completion(completion_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM completions WHERE id=?", (completion_id,))
        await db.commit()


async def recent_completions(limit: int = 20) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT c.id, c.task_id, c.completed_at, c.coins, t.title "
            "FROM completions c LEFT JOIN tasks t ON c.task_id = t.id "
            "ORDER BY c.id DESC LIMIT ?",
            (limit,),
        )
        rows = await cur.fetchall()
    return [
        {"id": r[0], "task_id": r[1], "completed_at": r[2],
         "coins": r[3], "title": r[4] or "(удалено)"}
        for r in rows
    ]


# ---------- RECURRING HELPERS ----------

async def shift_periods():
    """Сдвигает period_start у recurring, если период истёк."""
    today = date.today()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, period_days, period_start FROM tasks "
            "WHERE type='recurring' AND status='active' "
            "AND period_days IS NOT NULL AND period_start IS NOT NULL"
        )
        rows = await cur.fetchall()
        for task_id, pd, ps in rows:
            start = date.fromisoformat(ps)
            # если период закончился (сегодня > start + pd - 1)
            while (today - start).days >= pd:
                start = date.fromordinal(start.toordinal() + pd)
            if start.isoformat() != ps:
                await db.execute(
                    "UPDATE tasks SET period_start=? WHERE id=?",
                    (start.isoformat(), task_id),
                )
        await db.commit()
