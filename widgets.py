from __future__ import annotations

import html
import zlib
from datetime import datetime
from typing import ClassVar

from aiogram.methods.base import TelegramMethod
from aiogram.types import Message


class SendWidget(TelegramMethod[Message]):
    """Bot API 10.4 method not yet included in the project's aiogram version."""

    __returning__: ClassVar[type[Message]] = Message
    __api_method__: ClassVar[str] = "sendWidget"

    chat_id: int
    html: str
    caption: str | None = None
    allow_queries: bool = False
    is_shared: bool = False


VISIBLE_PRODUCTS = 6


def _quantity(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def render_stock_widget(products: list[dict], generated_at: datetime | None = None) -> str:
    """Render a compact, read-only stock snapshot for Telegram's HTML widget."""
    total_units = sum(int(product["quantity"]) for product in products)
    shown_products = products[:VISIBLE_PRODUCTS]
    timestamp = (generated_at or datetime.now().astimezone()).strftime("%d.%m.%Y · %H:%M")

    if shown_products:
        rows = []
        for product in shown_products:
            quantity = int(product["quantity"])
            availability = "available" if quantity else "empty"
            rows.append(
                '<div class="product">'
                '<span class="indicator ' + availability + '"></span>'
                '<span class="product-name">' + html.escape(str(product["display_name"])) + '</span>'
                '<strong class="product-quantity">' + _quantity(quantity) + '<small> шт.</small></strong>'
                '</div>'
            )
        inventory = '<div class="products">' + "".join(rows) + "</div>"
    else:
        inventory = (
            '<div class="empty-state"><span class="empty-icon">＋</span>'
            '<strong>Склад пока пуст</strong>'
            '<span>Добавьте первый товар через меню бота</span></div>'
        )

    more = ""
    if len(products) > VISIBLE_PRODUCTS:
        more = (
            '<div class="more">Показаны первые ' + str(VISIBLE_PRODUCTS) + ' из '
            + str(len(products)) + ' · полный список: /list</div>'
        )

    document = (
        '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width, initial-scale=1"><style>'
        ':root{color-scheme:light dark}'
        '*{box-sizing:border-box}'
        'body{margin:0;padding:12px 12px calc(18px + env(safe-area-inset-bottom));'
        'font:14px/1.4 system-ui,sans-serif;color:var(--tg-theme-text-color,#1c1c1e)}'
        '.panel{display:flex;flex-direction:column;gap:14px}'
        '.heading{display:flex;align-items:center;gap:10px}'
        '.mark{width:38px;height:38px;display:flex;align-items:center;justify-content:center;'
        'border-radius:12px;background:var(--tg-theme-button-color,#3390ec);font-size:20px}'
        '.title{font-size:19px;font-weight:700;letter-spacing:-.3px}'
        '.subtitle{font-size:12px;color:var(--tg-theme-hint-color,#707579)}'
        '.metrics{display:grid;grid-template-columns:1fr 1fr;gap:9px}'
        '.metric{min-width:0;padding:11px 12px;border-radius:14px;'
        'background:var(--tg-theme-secondary-bg-color,#f1f1f1)}'
        '.metric-label{display:block;font-size:11px;color:var(--tg-theme-hint-color,#707579)}'
        '.metric-value{display:block;margin-top:3px;font-size:21px;line-height:1.15;font-weight:700;'
        'font-variant-numeric:tabular-nums}'
        '.section-head{display:flex;align-items:center;justify-content:space-between;margin:1px 1px 7px}'
        '.section-title{font-size:13px;font-weight:650}'
        '.count{font-size:11px;color:var(--tg-theme-hint-color,#707579)}'
        '.products{overflow:hidden;border-radius:14px;background:var(--tg-theme-secondary-bg-color,#f1f1f1)}'
        '.product{display:flex;align-items:center;gap:9px;min-height:43px;padding:8px 11px}'
        '.product+.product{border-top:1px solid var(--tg-theme-section-separator-color,rgba(127,127,127,.18))}'
        '.indicator{width:7px;height:7px;flex:0 0 7px;border-radius:50%}'
        '.available{background:#31a56a}.empty{background:var(--tg-theme-hint-color,#8e8e93)}'
        '.product-name{min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px}'
        '.product-quantity{flex:none;font-size:13px;font-variant-numeric:tabular-nums}'
        '.product-quantity small{font-size:10px;font-weight:500;color:var(--tg-theme-hint-color,#707579)}'
        '.empty-state{min-height:106px;display:flex;flex-direction:column;align-items:center;'
        'justify-content:center;gap:5px;padding:14px;border-radius:14px;'
        'background:var(--tg-theme-secondary-bg-color,#f1f1f1);text-align:center}'
        '.empty-icon{width:28px;height:28px;display:flex;align-items:center;justify-content:center;'
        'border-radius:50%;background:var(--tg-theme-bg-color,#fff);font-size:20px;'
        'color:var(--tg-theme-button-color,#3390ec)}'
        '.empty-state span:last-child{font-size:11px;color:var(--tg-theme-hint-color,#707579)}'
        '.more{margin-top:-7px;font-size:11px;color:var(--tg-theme-hint-color,#707579);text-align:center}'
        '.footer{display:flex;justify-content:space-between;gap:8px;font-size:10px;'
        'color:var(--tg-theme-hint-color,#707579)}'
        '</style></head><body><main class="panel">'
        '<header class="heading"><div class="mark">📦</div><div><div class="title">Панель склада</div>'
        '<div class="subtitle">Сводка по текущим остаткам</div></div></header>'
        '<section class="metrics"><div class="metric"><span class="metric-label">Позиций</span>'
        '<strong class="metric-value">' + _quantity(len(products)) + '</strong></div>'
        '<div class="metric"><span class="metric-label">Всего единиц</span>'
        '<strong class="metric-value">' + _quantity(total_units) + '</strong></div></section>'
        '<section><div class="section-head"><strong class="section-title">Товары</strong>'
        '<span class="count">' + str(min(len(products), VISIBLE_PRODUCTS)) + ' из '
        + str(len(products)) + '</span></div>' + inventory + '</section>'
        + more + '<footer class="footer"><span>Обновлено при открытии</span>'
        '<span>' + html.escape(timestamp) + '</span></footer></main></body></html>'
    )

    encoded = document.encode("utf-8")
    if b"\0" in encoded or len(encoded) > 32_768 or len(zlib.compress(encoded, 9)) > 4_096:
        raise ValueError("Telegram widget HTML exceeds the Bot API size limit")
    return document


def stock_widget_caption(products: list[dict]) -> str:
    """Accessible fallback for Telegram clients that do not render widgets."""
    total_units = sum(int(product["quantity"]) for product in products)
    return f"Склад: {len(products)} позиций · {_quantity(total_units)} шт. Полный список: /list"
