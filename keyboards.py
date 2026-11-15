from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


ADD = "➕ Добавить товар"
WRITE_OFF = "📤 Списать товар"
STOCK = "📦 Остатки"
SEARCH = "🔎 Найти товар"
DELETE = "🗑 Удалить товар"
HISTORY = "🕘 История операций"
CLEANUP = "🧹 Автоудаление (вкл/выкл)"


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADD), KeyboardButton(text=WRITE_OFF)],
            [KeyboardButton(text=STOCK), KeyboardButton(text=SEARCH)],
            [KeyboardButton(text=DELETE), KeyboardButton(text=HISTORY)],
            [KeyboardButton(text=CLEANUP)],
        ],
        resize_keyboard=True,
    )


def product_choices(products: list[dict], action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"📦 {product['display_name']} — {product['quantity']} шт.",
                callback_data=f"{action}:{product['id']}",
            )]
            for product in products
        ]
    )


def delete_confirmation(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"delete:yes:{product_id}"),
        InlineKeyboardButton(text="↩️ Отмена", callback_data="delete:no"),
    ]])
