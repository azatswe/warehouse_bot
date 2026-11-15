import logging
import re
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ErrorEvent, Message

import keyboards
from database import Database

logger = logging.getLogger(__name__)
router = Router()


class AddFlow(StatesGroup):
    name = State()
    quantity = State()


class WriteOffFlow(StatesGroup):
    quantity = State()


class SearchFlow(StatesGroup):
    query = State()


class DeleteFlow(StatesGroup):
    confirmation = State()


def user_name(message: Message) -> str:
    user = message.from_user
    return user.full_name or user.username or str(user.id)


async def prompt_add_name(message: Message, state: FSMContext) -> None:
    await state.set_state(AddFlow.name)
    await message.answer("Введите вид (название) товара")


async def start_add(message: Message, state: FSMContext) -> None:
    await state.clear()
    await prompt_add_name(message, state)


async def start_write_off(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    products = await db.list_products()
    if not products:
        await message.answer("Склад пуст, списывать нечего", reply_markup=keyboards.main_menu())
        return
    await message.answer("Выберите товар для списания:", reply_markup=keyboards.product_choices(products, "writeoff"))


async def start_delete(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    products = await db.list_products()
    if not products:
        await message.answer("Склад пуст. Добавьте первый товар", reply_markup=keyboards.main_menu())
        return
    await message.answer("Выберите товар для удаления:", reply_markup=keyboards.product_choices(products, "delete"))


async def show_stock(message: Message, db: Database) -> None:
    products = await db.list_products()
    if not products:
        await message.answer("Склад пуст. Добавьте первый товар", reply_markup=keyboards.main_menu())
        return

    total = sum(product["quantity"] for product in products)
    lines = ["Остатки на складе:"]
    lines.extend(f"{index}. {product['display_name']} — {product['quantity']} шт."
                 for index, product in enumerate(products, start=1))
    lines.append(f"Всего позиций: {len(products)} · Всего единиц: {total}")
    chunks: list[str] = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > 4000:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    for index, chunk in enumerate(chunks):
        await message.answer(chunk, reply_markup=keyboards.main_menu() if index == len(chunks) - 1 else None)


async def search_and_reply(message: Message, db: Database, query: str) -> None:
    products = await db.search_products(query)
    if not products:
        await message.answer("Ничего не найдено", reply_markup=keyboards.main_menu())
        return
    lines = [f"{product['display_name']} — {product['quantity']} шт." for product in products]
    await message.answer("\n".join(lines), reply_markup=keyboards.main_menu())


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню", reply_markup=keyboards.main_menu())


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено", reply_markup=keyboards.main_menu())


@router.message(Command("list"))
async def list_command(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    await show_stock(message, db)


@router.message(Command("find"))
async def find_command(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    query = (message.text or "").partition(" ")[2].strip()
    if not query:
        await message.answer("Использование: /find <часть названия>", reply_markup=keyboards.main_menu())
        return
    await search_and_reply(message, db, query)


# Menu actions are registered before state handlers so a menu tap restarts that flow.
@router.message(F.text == keyboards.ADD)
async def add_menu(message: Message, state: FSMContext) -> None:
    await start_add(message, state)


@router.message(F.text == keyboards.WRITE_OFF)
async def write_off_menu(message: Message, state: FSMContext, db: Database) -> None:
    await start_write_off(message, state, db)


@router.message(F.text == keyboards.STOCK)
async def stock_menu(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    await show_stock(message, db)


@router.message(F.text == keyboards.SEARCH)
async def search_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SearchFlow.query)
    await message.answer("Введите часть названия товара")


@router.message(F.text == keyboards.DELETE)
async def delete_menu(message: Message, state: FSMContext, db: Database) -> None:
    await start_delete(message, state, db)


@router.message(F.text == keyboards.HISTORY)
async def history_menu(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    entries = await db.history(20)
    if not entries:
        await message.answer("История операций пуста", reply_markup=keyboards.main_menu())
        return
    lines = []
    for item in entries:
        timestamp = datetime.fromisoformat(item["created_at"]).astimezone().strftime("%d.%m.%Y %H:%M")
        change = f"{item['delta']:+d}".replace("-", "−")
        lines.append(f"{timestamp} — {item['user_name']}: {change} {item['product_name']}")
    await message.answer("\n".join(lines), reply_markup=keyboards.main_menu())


@router.message(AddFlow.name)
async def receive_product_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not 2 <= len(name) <= 100:
        await message.answer("Название должно содержать от 2 до 100 символов. Введите вид (название) товара")
        return
    await state.update_data(product_name=name)
    await state.set_state(AddFlow.quantity)
    await message.answer("Введите количество")


@router.message(AddFlow.quantity)
async def receive_add_quantity(message: Message, state: FSMContext, db: Database) -> None:
    text = (message.text or "").strip()
    if not re.fullmatch(r"[0-9]+", text):
        await message.answer("Введите целое число больше 0 (максимум 1 000 000). Введите количество")
        return
    digits = text.lstrip("0") or "0"
    if len(digits) > 7:
        await message.answer("Количество должно быть от 1 до 1 000 000. Введите количество")
        return
    quantity = int(digits)
    if not 1 <= quantity <= 1_000_000:
        await message.answer("Количество должно быть от 1 до 1 000 000. Введите количество")
        return
    data = await state.get_data()
    total = await db.add_product(data["product_name"], quantity, message.from_user.id, user_name(message))
    await state.clear()
    await message.answer(
        f"Добавлено: {data['product_name']} — {quantity} шт. Всего на складе: {total} шт.",
        reply_markup=keyboards.main_menu(),
    )


@router.callback_query(F.data.startswith("writeoff:"))
async def choose_write_off(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    product = await db.get_product(product_id)
    if product is None:
        await callback.answer("Товар больше не существует", show_alert=True)
        await state.clear()
        return
    await state.update_data(product_id=product_id, product_name=product["display_name"])
    await state.set_state(WriteOffFlow.quantity)
    await callback.answer()
    await callback.message.answer(f"Введите количество для списания: {product['display_name']}")


@router.message(WriteOffFlow.quantity)
async def receive_write_off_quantity(message: Message, state: FSMContext, db: Database) -> None:
    text = (message.text or "").strip()
    if not re.fullmatch(r"[0-9]+", text):
        await message.answer("Введите целое число больше 0. Введите количество для списания")
        return
    digits = text.lstrip("0") or "0"
    if len(digits) > 18 or int(digits) <= 0:
        await message.answer("Введите целое число больше 0. Введите количество для списания")
        return
    quantity = int(digits)
    data = await state.get_data()
    result = await db.remove_quantity(data["product_id"], quantity, message.from_user.id, user_name(message))
    if result is None:
        await state.clear()
        await message.answer("Товар больше не существует", reply_markup=keyboards.main_menu())
    elif not result[0]:
        await message.answer(f"На складе только {result[1]} шт. Введите количество для списания")
    else:
        await state.clear()
        await message.answer(f"Списано {quantity} шт. Осталось: {result[1]} шт.", reply_markup=keyboards.main_menu())


@router.message(SearchFlow.query)
async def receive_search_query(message: Message, state: FSMContext, db: Database) -> None:
    query = (message.text or "").strip()
    if not query:
        await message.answer("Введите часть названия товара")
        return
    await state.clear()
    await search_and_reply(message, db, query)


@router.callback_query(F.data.startswith("delete:"))
async def choose_delete(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    parts = callback.data.split(":")
    if parts[1] == "no":
        await state.clear()
        await callback.answer("Удаление отменено")
        await callback.message.answer("Удаление отменено", reply_markup=keyboards.main_menu())
        return
    if parts[1] == "yes":
        product_id = int(parts[2])
        deleted = await db.delete_product(product_id, callback.from_user.id,
                                          callback.from_user.full_name or callback.from_user.username or str(callback.from_user.id))
        await state.clear()
        await callback.answer()
        await callback.message.answer("Товар удалён" if deleted else "Товар больше не существует",
                                      reply_markup=keyboards.main_menu())
        return
    product_id = int(parts[1])
    product = await db.get_product(product_id)
    if product is None:
        await state.clear()
        await callback.answer("Товар больше не существует", show_alert=True)
        return
    await state.update_data(product_id=product_id)
    await state.set_state(DeleteFlow.confirmation)
    await callback.answer()
    await callback.message.answer(f"Удалить товар «{product['display_name']}»?",
                                  reply_markup=keyboards.delete_confirmation(product_id))


@router.message(DeleteFlow.confirmation)
async def repeat_delete_confirmation(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    product = await db.get_product(data["product_id"])
    if product is None:
        await state.clear()
        await message.answer("Товар больше не существует", reply_markup=keyboards.main_menu())
        return
    await message.answer(
        f"Подтвердите удаление «{product['display_name']}» кнопкой ниже.",
        reply_markup=keyboards.delete_confirmation(product["id"]),
    )


@router.message(StateFilter(AddFlow.name, AddFlow.quantity, WriteOffFlow.quantity,
                            SearchFlow.query, DeleteFlow.confirmation), lambda message: message.text is None)
async def reject_non_text(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    prompts = {
        AddFlow.name.state: "Введите вид (название) товара",
        AddFlow.quantity.state: "Введите количество",
        WriteOffFlow.quantity.state: "Введите количество для списания",
        SearchFlow.query.state: "Введите часть названия товара",
        DeleteFlow.confirmation.state: "Подтвердите удаление кнопкой «Да, удалить» или «Отмена»",
    }
    await message.answer(f"Пожалуйста, отправьте текст. {prompts.get(current, '')}")


@router.errors()
async def handle_error(event: ErrorEvent) -> bool:
    error = event.exception
    logger.error("Ошибка при обработке обновления Telegram", exc_info=(type(error), error, error.__traceback__))
    update = event.update
    message = update.message or (update.callback_query.message if update.callback_query else None)
    if message:
        await message.answer("Что-то пошло не так, попробуйте ещё раз")
    return True
