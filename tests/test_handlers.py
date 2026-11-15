import tempfile
import unittest
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, SendMessage
from aiogram.types import CallbackQuery, Chat, InlineKeyboardMarkup, Message, PhotoSize, Update, User

from database import Database
from handlers import router
from main import AllowedUsersMiddleware
from widgets import SendWidget


class RecordingSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.sent_messages = []
        self.reject_widgets = False

    async def close(self):
        return None

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, SendMessage):
            message = Message(
                message_id=len(self.calls),
                date=datetime.now(timezone.utc),
                chat=Chat(id=method.chat_id, type="private"),
                from_user=User(id=bot.id, is_bot=True, first_name="Warehouse"),
                text=method.text,
                reply_markup=method.reply_markup if isinstance(method.reply_markup, InlineKeyboardMarkup) else None,
            )
            self.sent_messages.append(message)
            return message
        if isinstance(method, SendWidget):
            if self.reject_widgets:
                raise TelegramBadRequest(method=method, message="INPUT_MEDIA_WIDGET_NOT_ALLOWED")
            message = Message(
                message_id=len(self.calls),
                date=datetime.now(timezone.utc),
                chat=Chat(id=method.chat_id, type="private"),
                from_user=User(id=bot.id, is_bot=True, first_name="Warehouse"),
                caption=method.caption,
            )
            self.sent_messages.append(message)
            return message
        if isinstance(method, AnswerCallbackQuery):
            return True
        raise AssertionError(f"Unexpected Telegram method: {type(method).__name__}")

    async def stream_content(self, url, headers=None, timeout=30, chunk_size=65536, raise_for_status=True):
        if False:
            yield b""


class FailingDatabase:
    async def list_products(self):
        raise RuntimeError("test database failure")


class HandlerFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = RecordingSession()
        self.bot = Bot("42:" + "x" * 35, session=self.session)
        self.dispatcher = Dispatcher(storage=MemoryStorage())
        # Use one on-disk database because each operation opens its own SQLite connection.
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(f"{self.temp_dir.name}/warehouse.db")
        await self.db.initialize()
        self.dispatcher["db"] = self.db
        self.dispatcher.message.outer_middleware(AllowedUsersMiddleware(frozenset({42})))
        self.dispatcher.callback_query.outer_middleware(AllowedUsersMiddleware(frozenset({42})))
        self.dispatcher.include_router(router)
        self.update_id = 0

    async def asyncTearDown(self):
        await self.dispatcher.storage.close()
        await self.bot.session.close()
        self.temp_dir.cleanup()

    async def send_text(self, text, chat_type="private"):
        self.update_id += 1
        message = Message(
            message_id=self.update_id,
            date=datetime.now(timezone.utc),
            chat=Chat(id=42 if chat_type == "private" else -42, type=chat_type),
            from_user=User(id=42, is_bot=False, first_name="Azat"),
            text=text,
        )
        await self.dispatcher.feed_update(self.bot, Update(update_id=self.update_id, message=message))

    async def send_callback(self, data, message):
        self.update_id += 1
        callback = CallbackQuery(
            id=f"callback-{self.update_id}",
            from_user=User(id=42, is_bot=False, first_name="Azat"),
            chat_instance="private-chat",
            message=message,
            data=data,
        )
        await self.dispatcher.feed_update(self.bot, Update(update_id=self.update_id, callback_query=callback))

    async def send_photo(self):
        self.update_id += 1
        message = Message(
            message_id=self.update_id,
            date=datetime.now(timezone.utc),
            chat=Chat(id=42, type="private"),
            from_user=User(id=42, is_bot=False, first_name="Azat"),
            photo=[PhotoSize(file_id="photo-id", file_unique_id="photo-unique", width=1, height=1)],
        )
        await self.dispatcher.feed_update(self.bot, Update(update_id=self.update_id, message=message))

    def replies(self):
        return [call.text for call in self.session.calls if isinstance(call, SendMessage)]

    async def test_main_user_flows_and_recovery_paths(self):
        await self.send_text("/start")
        menu = self.session.calls[0].reply_markup
        self.assertEqual(
            {button.text for row in menu.keyboard for button in row},
            {"Добавить товар", "Списать товар", "Остатки", "Найти товар", "Удалить товар", "История операций", "📊 Панель склада"},
        )
        await self.send_text("Добавить товар")
        await self.send_photo()

        self.assertIn("Пожалуйста, отправьте текст", self.replies()[-1])
        await self.send_text("A")
        self.assertIn("от 2 до 100 символов", self.replies()[-1])
        await self.send_text("X" * 101)
        self.assertIn("от 2 до 100 символов", self.replies()[-1])
        await self.send_text("Фильтр")
        self.assertEqual(self.replies()[-1], "Введите количество")
        await self.send_photo()
        self.assertIn("Пожалуйста, отправьте текст", self.replies()[-1])
        await self.send_text("abc")
        self.assertIn("Введите целое число больше 0", self.replies()[-1])
        await self.send_text("0")
        self.assertIn("больше 0", self.replies()[-1])
        await self.send_text("-1")
        self.assertIn("больше 0", self.replies()[-1])
        await self.send_text("1000001")
        self.assertIn("1 000 000", self.replies()[-1])
        await self.send_text("0003")

        # Same item with different case and repeated spaces increments existing stock.
        await self.send_text("Добавить товар")
        await self.send_text("  ФИЛЬТР  ")
        await self.send_text("2")
        products = await self.db.list_products()
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["quantity"], 5)
        product_id = products[0]["id"]

        await self.send_text("Остатки")
        self.assertIn("Всего позиций: 1 · Всего единиц: 5", self.replies()[-1])
        await self.send_text("/list")
        self.assertIn("Фильтр — 5 шт.", self.replies()[-1])
        await self.send_text("/find иЛЬТ")
        self.assertIn("Фильтр — 5 шт.", self.replies()[-1])

        # Oversized write-off must keep the dialogue open; zero stock must remain selectable.
        await self.send_text("Списать товар")
        choice_message = self.session.sent_messages[-1]
        choice_data = [button.callback_data for row in choice_message.reply_markup.inline_keyboard for button in row]
        self.assertIn(f"writeoff:{product_id}", choice_data)
        await self.send_callback(f"writeoff:{product_id}", choice_message)
        await self.send_text("6")
        self.assertIn("На складе только 5 шт.", self.replies()[-1])
        await self.send_text("5")
        self.assertIn("Списано 5 шт. Осталось: 0 шт.", self.replies()[-1])
        self.assertEqual((await self.db.get_product(product_id))["quantity"], 0)
        await self.send_text("Списать товар")
        choice_message = self.session.sent_messages[-1]
        await self.send_callback(f"writeoff:{product_id}", choice_message)
        await self.send_text("1")
        self.assertIn("На складе только 0 шт.", self.replies()[-1])
        await self.send_text("/cancel")

        # Search menu and /find share case-insensitive substring behavior.
        await self.send_text("Найти товар")
        await self.send_text("ильт")
        self.assertIn("Фильтр — 0 шт.", self.replies()[-1])
        await self.send_text("Найти товар")
        await self.send_text("НЕТ ТАКОГО")
        self.assertEqual(self.replies()[-1], "Ничего не найдено")

        # Deletion is canceled once, then confirmed; only the confirmed delete is logged.
        await self.send_text("Удалить товар")
        choice_message = self.session.sent_messages[-1]
        choice_data = [button.callback_data for row in choice_message.reply_markup.inline_keyboard for button in row]
        self.assertIn(f"delete:{product_id}", choice_data)
        await self.send_callback(f"delete:{product_id}", choice_message)
        confirmation_message = self.session.sent_messages[-1]
        confirmation_data = [button.callback_data for row in confirmation_message.reply_markup.inline_keyboard for button in row]
        self.assertEqual(set(confirmation_data), {"delete:no", f"delete:yes:{product_id}"})
        await self.send_photo()
        self.assertIn("Пожалуйста, отправьте текст", self.replies()[-1])
        await self.send_text("передумал")
        self.assertIn("Подтвердите удаление", self.replies()[-1])
        confirmation_message = self.session.sent_messages[-1]
        await self.send_callback("delete:no", confirmation_message)
        self.assertIsNotNone(await self.db.get_product(product_id))
        await self.send_text("Удалить товар")
        choice_message = self.session.sent_messages[-1]
        await self.send_callback(f"delete:{product_id}", choice_message)
        confirmation_message = self.session.sent_messages[-1]
        await self.send_callback(f"delete:yes:{product_id}", confirmation_message)
        self.assertIsNone(await self.db.get_product(product_id))
        await self.send_text("История операций")
        history_text = self.replies()[-1]
        self.assertIn("+3 Фильтр", history_text)
        self.assertIn("+2 ФИЛЬТР", history_text)
        self.assertIn("−5 Фильтр", history_text)
        self.assertIn("−0 Фильтр", history_text)

        await self.send_text("Остатки")
        self.assertEqual(self.replies()[-1], "Склад пуст. Добавьте первый товар")

        # A menu button replaces an active flow, while /cancel clears it.
        await self.send_text("Найти товар")
        await self.send_text("Добавить товар")
        self.assertEqual(self.replies()[-1], "Введите вид (название) товара")
        await self.send_text("Масло")
        await self.send_text("/cancel")
        await self.send_text("1")
        self.assertEqual(await self.db.list_products(), [])

        await self.send_text("Добавить товар")
        await self.send_text("Граничный товар")
        await self.send_text("1000000")
        products = await self.db.list_products()
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["quantity"], 1_000_000)

        await self.send_text("/widget")
        widget = self.session.calls[-1]
        self.assertIsInstance(widget, SendWidget)
        self.assertEqual(widget.chat_id, 42)
        self.assertFalse(widget.allow_queries)
        self.assertFalse(widget.is_shared)
        self.assertIn("Склад", widget.html)
        self.assertIn("const TOTAL_UNITS=1000000", widget.html)
        self.assertIn("Полный список: /list", widget.caption)
        self.assertLessEqual(len(widget.html.encode("utf-8")), 32_768)

        await self.send_text("/widget", chat_type="group")
        self.assertIsInstance(self.session.calls[-1], SendMessage)
        self.assertIn("только в личном чате", self.session.calls[-1].text)

        self.session.reject_widgets = True
        await self.send_text("/widget")
        self.assertIn("Telegram API отклонил HTML-панель для этого бота", self.replies()[-1])
        self.assertNotIn("Граничный товар", self.replies()[-1])

        self.dispatcher["db"] = FailingDatabase()
        with self.assertLogs("handlers.stock", level="ERROR"):
            await self.send_text("/list")
        self.assertEqual(self.replies()[-1], "Что-то пошло не так, попробуйте ещё раз")

if __name__ == "__main__":
    unittest.main()
