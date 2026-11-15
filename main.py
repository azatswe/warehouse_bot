import asyncio
import logging

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.types import CallbackQuery, Message

from config import load_config
from database import Database
from handlers import router


class AllowedUsersMiddleware(BaseMiddleware):
    def __init__(self, allowed_users: frozenset[int]):
        self.allowed_users = allowed_users

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is None or user.id not in self.allowed_users:
            if isinstance(event, Message):
                await event.answer("У вас нет доступа")
            elif isinstance(event, CallbackQuery):
                await event.answer("У вас нет доступа", show_alert=True)
            return None
        db = data.get("db")
        data["cleanup_enabled"] = False
        if user is not None and db is not None:
            try:
                data["cleanup_enabled"] = await db.cleanup_enabled(user.id)
            except Exception as exc:
                logging.getLogger(__name__).debug("Could not read chat cleanup setting: %s", exc)
        try:
            return await handler(event, data)
        finally:
            if isinstance(event, Message) and event.chat.type == "private":
                try:
                    if db and user and await db.cleanup_enabled(user.id):
                        await event.delete()
                except Exception as exc:
                    logging.getLogger(__name__).debug("Could not clean up private chat input: %s", exc)


async def main() -> None:
    config = load_config()
    db = Database(config.database_path)
    await db.initialize()

    bot = Bot(token=config.bot_token)
    dispatcher = Dispatcher()
    dispatcher["db"] = db
    dispatcher.message.outer_middleware(AllowedUsersMiddleware(config.allowed_users))
    dispatcher.callback_query.outer_middleware(AllowedUsersMiddleware(config.allowed_users))
    dispatcher.include_router(router)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main())
