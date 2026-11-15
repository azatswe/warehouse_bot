import asyncio
import tempfile
import unittest
from pathlib import Path

from database import Database, normalize_name


class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp_dir.name) / "warehouse.db")
        self.db = Database(self.path)
        await self.db.initialize()

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_add_normalizes_name_and_persists_quantity(self):
        first = await self.db.add_product("Шины 205/55 R16", 20, 1, "Арслан")
        total = await self.db.add_product("  шины   205/55 r16 ", 5, 2, "Азамат")

        self.assertEqual(first, 20)
        self.assertEqual(total, 25)
        products = await self.db.list_products()
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["display_name"], "Шины 205/55 R16")

        reopened = Database(self.path)
        await reopened.initialize()
        self.assertEqual((await reopened.list_products())[0]["quantity"], 25)

    async def test_write_off_cannot_make_stock_negative(self):
        await self.db.add_product("Фильтр", 4, 1, "Арслан")
        product = (await self.db.list_products())[0]

        insufficient = await self.db.remove_quantity(product["id"], 5, 1, "Арслан")
        self.assertEqual(insufficient, (False, 4))
        self.assertEqual((await self.db.list_products())[0]["quantity"], 4)

        remaining = await self.db.remove_quantity(product["id"], 4, 1, "Арслан")
        self.assertEqual(remaining, (True, 0))

    async def test_zero_stock_cannot_be_written_off(self):
        await self.db.add_product("Нулевой остаток", 1, 1, "Арслан")
        product = (await self.db.list_products())[0]
        await self.db.remove_quantity(product["id"], 1, 1, "Арслан")

        result = await self.db.remove_quantity(product["id"], 1, 1, "Арслан")
        self.assertEqual(result, (False, 0))
        self.assertEqual((await self.db.list_products())[0]["quantity"], 0)

    async def test_concurrent_additions_do_not_lose_updates(self):
        await asyncio.gather(*(
            self.db.add_product("Перчатки", 1, user_id, f"Пользователь {user_id}")
            for user_id in range(1, 11)
        ))

        products = await self.db.list_products()
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["quantity"], 10)
        self.assertEqual(len(await self.db.history(20)), 10)

    async def test_concurrent_writeoffs_never_go_below_zero(self):
        await self.db.add_product("Крепёж", 5, 1, "Арслан")
        product = (await self.db.list_products())[0]
        results = await asyncio.gather(*(
            self.db.remove_quantity(product["id"], 1, user_id, f"Пользователь {user_id}")
            for user_id in range(1, 11)
        ))

        self.assertEqual(sum(1 for result in results if result[0]), 5)
        self.assertEqual(sum(1 for result in results if not result[0]), 5)
        self.assertEqual((await self.db.list_products())[0]["quantity"], 0)
        self.assertEqual(len(await self.db.history(20)), 6)

    async def test_products_are_sorted_and_search_is_case_insensitive(self):
        await self.db.add_product("Шины 205", 1, 1, "Арслан")
        await self.db.add_product("Масло", 1, 1, "Арслан")
        await self.db.add_product("Фильтр", 1, 1, "Арслан")

        products = await self.db.list_products()
        self.assertEqual([product["display_name"] for product in products], ["Масло", "Фильтр", "Шины 205"])
        self.assertEqual([product["display_name"] for product in await self.db.search_products("шИны")], ["Шины 205"])
        self.assertEqual(await self.db.search_products("не найдено"), [])

    async def test_history_returns_only_latest_twenty_operations(self):
        for index in range(25):
            await self.db.add_product("Товар", 1, index, f"Пользователь {index}")

        history = await self.db.history(20)
        self.assertEqual(len(history), 20)
        self.assertEqual(history[0]["user_id"], 24)
        self.assertEqual(history[-1]["user_id"], 5)

    async def test_delete_records_negative_balance(self):
        await self.db.add_product("Масло", 7, 5, "Арслан")
        product = (await self.db.list_products())[0]

        self.assertTrue(await self.db.delete_product(product["id"], 5, "Арслан"))
        self.assertEqual(await self.db.list_products(), [])
        history = await self.db.history()
        self.assertEqual(history[0]["action"], "delete")
        self.assertEqual(history[0]["delta"], -7)

    async def test_normalization_collapses_whitespace_and_casefolds(self):
        self.assertEqual(normalize_name("  ШИНЫ \t205/55  "), "шины 205/55")


if __name__ == "__main__":
    unittest.main()
