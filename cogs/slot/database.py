import aiosqlite
from typing import Dict

class Database:
    def __init__(self):
        self.db = None

    async def init(self):
        self.db = await aiosqlite.connect("slot_data.db")
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 10000,
                current_bet INTEGER DEFAULT 1000,
                jp_gauge INTEGER DEFAULT 0
            )
        """)
        await self.db.commit()

    async def get_user(self, user_id: str) -> Dict:
        async with self.db.execute(
            "SELECT balance, current_bet, jp_gauge FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"balance": row[0], "current_bet": row[1], "jp_gauge": row[2]}
        
        await self.db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        await self.db.commit()
        return {"balance": 10000, "current_bet": 1000, "jp_gauge": 0}

    async def update_user(self, user_id: str, **kwargs):
        if not kwargs:
            return
        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [user_id]
        await self.db.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
        await self.db.commit()

db = Database()