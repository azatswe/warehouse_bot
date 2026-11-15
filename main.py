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
        return await handler(event, data)


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
