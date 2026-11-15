import unittest
import zlib
from datetime import datetime, timezone

from widgets import SendWidget, render_stock_widget, stock_widget_caption


class StockWidgetTests(unittest.TestCase):
    def test_dashboard_shows_summary_stock_and_escapes_product_names(self):
        html = render_stock_widget([
            {"display_name": "Масло 5W-30", "quantity": 1_250},
            {"display_name": "<script>alert(1)</script>", "quantity": 0},
        ], datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc))

        self.assertIn("Панель склада", html)
        self.assertIn("1 250", html)
        self.assertIn("15.11.2026 · 09:00", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn('class="indicator empty"', html)

    def test_empty_state_and_caption_remain_useful_on_unsupported_clients(self):
        self.assertIn("Склад пока пуст", render_stock_widget([]))
        self.assertEqual(stock_widget_caption([]), "Склад: 0 позиций · 0 шт. Полный список: /list")

    def test_long_inventory_is_bounded_to_a_compact_widget(self):
        products = [{"display_name": f"Товар {index} " + "x" * 90, "quantity": index} for index in range(20)]
        html = render_stock_widget(products)

        self.assertIn("Показаны первые 6 из 20", html)
        self.assertEqual(html.count('class="product"'), 6)
        encoded = html.encode("utf-8")
        self.assertLessEqual(len(encoded), 32_768)
        self.assertLessEqual(len(zlib.compress(encoded, 9)), 4_096)

    def test_custom_api_method_is_read_only_and_uses_bot_api_104(self):
        method = SendWidget(chat_id=123, html="<b>Склад</b>", caption="Склад: 0")

        self.assertEqual(method.__api_method__, "sendWidget")
        self.assertEqual(method.chat_id, 123)
        self.assertFalse(method.allow_queries)
        self.assertFalse(method.is_shared)


if __name__ == "__main__":
    unittest.main()
