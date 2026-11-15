import json
import re
import unittest
import zlib
from html.parser import HTMLParser

from widgets import PAGE_SIZE, SendWidget, render_stock_widget, stock_widget_caption


class WidgetMarkupParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.tags.append(tag)


class StockWidgetTests(unittest.TestCase):
    def test_renders_native_themable_paged_snapshot(self):
        products = [
            {"display_name": f"Товар {index}", "quantity": index}
            for index in range(1, 19)
        ]
        widget = render_stock_widget(products)

        self.assertIn("--tg-theme-text-color", widget)
        self.assertIn("--tg-theme-button-color", widget)
        self.assertIn("replaceChildren", widget)
        self.assertIn("localStorage", widget)
        match = re.search(r"const ITEMS=(\[.*?\]);\nconst TOTAL=", widget, re.DOTALL)
        self.assertIsNotNone(match)
        self.assertEqual(len(json.loads(match.group(1))), 12)
        self.assertIn("const TOTAL=18", widget)
        self.assertIn("Полный список: /list", stock_widget_caption(products))
        self.assertEqual(PAGE_SIZE, 3)

    def test_user_names_are_script_safe_and_rendered_as_text(self):
        products = [{"display_name": "</script><script>alert(1)</script>", "quantity": 3}]
        widget = render_stock_widget(products)
        match = re.search(r"const ITEMS=(\[.*?\]);\nconst TOTAL=", widget, re.DOTALL)

        self.assertIsNotNone(match)
        decoded = json.loads(match.group(1))
        self.assertEqual(decoded[0]["n"], products[0]["display_name"])
        self.assertNotIn("</script><script>alert(1)", widget)
        self.assertIn("name.textContent=item.n", widget)
        self.assertNotIn("innerHTML", widget)

    def test_document_obeys_widget_profile_and_size_limits(self):
        products = [
            {"display_name": (f"Наименование {index} " + "оченьдлинное" * 7)[:100], "quantity": index}
            for index in range(100)
        ]
        widget = render_stock_widget(products)
        raw = widget.encode("utf-8")
        parser = WidgetMarkupParser()
        parser.feed(widget)

        self.assertNotIn(b"\0", raw)
        self.assertLessEqual(len(raw), 32_768)
        self.assertLessEqual(len(zlib.compress(raw, 9)), 4_096)
        self.assertEqual(parser.tags.count("style"), 1)
        self.assertEqual(parser.tags.count("script"), 1)
        self.assertNotIn("<meta", widget)
        self.assertNotIn("<input", widget)
        self.assertNotIn("<form", widget)
        self.assertNotIn("fetch(", widget)
        self.assertNotIn("100vh", widget)
        self.assertNotIn("overflow:auto", widget)
        self.assertNotIn("overflow:scroll", widget)
        self.assertNotIn("position:sticky", widget)
        self.assertIn("первые", widget)

    def test_empty_state_and_caption_are_useful(self):
        widget = render_stock_widget([])

        self.assertIn("Список пуст", widget)
        self.assertIn("Добавьте первый товар через меню", widget)
        self.assertEqual(stock_widget_caption([]), "Склад: 0 позиций · 0 шт. Полный список: /list")

    def test_bot_api_method_uses_read_only_private_widget_contract(self):
        method = SendWidget(
            chat_id=123,
            html=render_stock_widget([]),
            caption="Склад: 0 позиций · 0 шт. Полный список: /list",
        )

        self.assertEqual(method.__api_method__, "sendWidget")
        self.assertEqual(method.chat_id, 123)
        self.assertFalse(method.allow_queries)
        self.assertFalse(method.is_shared)
        self.assertEqual(method.caption, "Склад: 0 позиций · 0 шт. Полный список: /list")


if __name__ == "__main__":
    unittest.main()
