import unittest
from unittest.mock import AsyncMock

from handlers.stock import chunk_lines, show_stock


class LongListDatabase:
    async def list_products(self):
        return [
            {"display_name": f"Товар-{index:03d}-" + "x" * 88, "quantity": index}
            for index in range(80)
        ]


class RenderingTests(unittest.IsolatedAsyncioTestCase):
    async def test_stock_output_is_sorted_by_database_and_split_under_4000(self):
        message = AsyncMock()
        await show_stock(message, LongListDatabase())

        chunks = [call.args[0] for call in message.answer.await_args_list]
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 4000 for chunk in chunks))
        self.assertTrue(chunks[0].startswith("📦 Остатки на складе:"))
        self.assertIn("Позиций: 80 · Всего единиц: 3160", chunks[-1])
        self.assertEqual(sum(chunk.count(" — ") for chunk in chunks), 80)

    def test_chunk_lines_does_not_emit_empty_chunks(self):
        self.assertEqual(chunk_lines([]), [])
        self.assertEqual(chunk_lines(["a", "b"], limit=3), ["a\nb"])
        self.assertEqual(chunk_lines(["abcde"], limit=3), ["abc", "de"])


if __name__ == "__main__":
    unittest.main()
