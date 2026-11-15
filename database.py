from datetime import datetime
from pathlib import Path

import aiosqlite


def normalize_name(name: str) -> str:
    return " ".join(name.split()).casefold()


class Database:
    def __init__(self, path: str):
        self.path = path

    async def initialize(self) -> None:
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity >= 0),
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_name TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    user_name TEXT NOT NULL,
                    delta INTEGER NOT NULL,
                    action TEXT NOT NULL CHECK (action IN ('add', 'remove', 'delete')),
                    created_at TEXT NOT NULL
                );
            """)
            await db.commit()

    async def add_product(self, display_name: str, quantity: int, user_id: int, user_name: str) -> int:
        normalized = normalize_name(display_name)
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        async with aiosqlite.connect(self.path) as db:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                "INSERT INTO products(name, display_name, quantity, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET quantity = quantity + excluded.quantity, updated_at = excluded.updated_at",
                (normalized, display_name.strip(), quantity, now),
            )
            row = await (await db.execute("SELECT id, quantity FROM products WHERE name = ?", (normalized,))).fetchone()
            await db.execute(
                "INSERT INTO operations(product_name, user_id, user_name, delta, action, created_at) VALUES (?, ?, ?, ?, 'add', ?)",
                (display_name.strip(), user_id, user_name, quantity, now),
            )
            await db.commit()
            return int(row[1])

    async def list_products(self) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute(
                "SELECT id, name, display_name, quantity, updated_at FROM products"
            )).fetchall()
            return sorted((dict(row) for row in rows), key=lambda row: (row["display_name"].casefold(), row["name"]))

    async def get_product(self, product_id: int) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            row = await (await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))).fetchone()
            return dict(row) if row else None

    async def search_products(self, query: str) -> list[dict]:
        needle = normalize_name(query)
        products = await self.list_products()
        return [product for product in products if needle in product["name"]]

    async def remove_quantity(self, product_id: int, quantity: int, user_id: int, user_name: str) -> tuple[bool, int] | None:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        async with aiosqlite.connect(self.path) as db:
            await db.execute("BEGIN IMMEDIATE")
            row = await (await db.execute("SELECT display_name, quantity FROM products WHERE id = ?", (product_id,))).fetchone()
            if row is None:
                await db.rollback()
                return None
            name, current = row
            if quantity > current:
                await db.rollback()
                return False, int(current)
            remaining = current - quantity
            await db.execute("UPDATE products SET quantity = ?, updated_at = ? WHERE id = ?", (remaining, now, product_id))
            await db.execute(
                "INSERT INTO operations(product_name, user_id, user_name, delta, action, created_at) VALUES (?, ?, ?, ?, 'remove', ?)",
                (name, user_id, user_name, -quantity, now),
            )
            await db.commit()
            return True, remaining

    async def delete_product(self, product_id: int, user_id: int, user_name: str) -> bool:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        async with aiosqlite.connect(self.path) as db:
            await db.execute("BEGIN IMMEDIATE")
            row = await (await db.execute("SELECT display_name, quantity FROM products WHERE id = ?", (product_id,))).fetchone()
            if row is None:
                await db.rollback()
                return False
            name, quantity = row
            await db.execute(
                "INSERT INTO operations(product_name, user_id, user_name, delta, action, created_at) VALUES (?, ?, ?, ?, 'delete', ?)",
                (name, user_id, user_name, -int(quantity), now),
            )
            await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
            await db.commit()
            return True

    async def history(self, limit: int = 20) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute(
                "SELECT product_name, user_id, user_name, delta, action, created_at "
                "FROM operations ORDER BY id DESC LIMIT ?", (limit,),
            )).fetchall()
            return [dict(row) for row in rows]
