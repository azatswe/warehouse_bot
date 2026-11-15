import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    allowed_users: frozenset[int]
    database_path: str


def load_config() -> Config:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN не задан в .env")

    raw_users = os.getenv("ALLOWED_USERS", "")
    try:
        users = frozenset(int(value.strip()) for value in raw_users.split(",") if value.strip())
    except ValueError as exc:
        raise RuntimeError("ALLOWED_USERS должен содержать Telegram ID через запятую") from exc
    if not users:
        raise RuntimeError("Укажите хотя бы один Telegram ID в ALLOWED_USERS")

    return Config(
        bot_token=token,
        allowed_users=users,
        database_path=os.getenv("DATABASE_PATH", "warehouse.db").strip() or "warehouse.db",
    )
