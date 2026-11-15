from __future__ import annotations

import json
import zlib
from typing import ClassVar

from aiogram.methods.base import TelegramMethod
from aiogram.types import Message


class SendWidget(TelegramMethod[Message]):
    """Bot API 10.4 method, typed locally until aiogram adds it."""

    __returning__: ClassVar[type[Message]] = Message
    __api_method__: ClassVar[str] = "sendWidget"

    chat_id: int
    html: str
    caption: str | None = None
    allow_queries: bool = False
    is_shared: bool = False


PAGE_SIZE = 3
MAX_PRODUCTS_IN_HTML = 12
TARGET_COMPRESSED_BYTES = 3_800

_STYLE = """<style>
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{font-family:system-ui,sans-serif;color:var(--tg-theme-text-color)}
.panel{display:flex;flex-direction:column;gap:.8em}
.heading{display:flex;align-items:center;gap:.65em}
.mark{display:flex;align-items:center;justify-content:center;width:2.5em;height:2.5em;flex:none;border-radius:.8em;background:var(--tg-theme-button-color);color:var(--tg-theme-button-text-color);font-size:1.1em}
.title{font-size:1.12em;font-weight:700;letter-spacing:-.02em}
.subtitle,.muted{color:var(--tg-theme-hint-color);font-size:.82em}
.metrics{display:grid;grid-template-columns:1fr 1fr;gap:.55em}
.metric{min-width:0;padding:.65em .75em;border-radius:.85em;background:var(--tg-theme-secondary-bg-color)}
.metric-label{display:block;color:var(--tg-theme-hint-color);font-size:.76em}
.metric-value{display:block;margin-top:.12em;font-size:1.25em;line-height:1.15;font-weight:700;font-variant-numeric:tabular-nums}
.section-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:.4em}
.section-title{font-size:.9em;font-weight:650}
.products{overflow:hidden;border-radius:.85em;background:var(--tg-theme-secondary-bg-color)}
.row{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:.5em;min-height:2.6em;padding:.48em .7em}
.row+.row{border-top:1px solid var(--tg-theme-section-separator-color)}
.name{min-width:0;overflow-wrap:anywhere;font-size:.86em;line-height:1.25;user-select:text;-webkit-user-select:text}
.quantity{white-space:nowrap;font-size:.86em;font-weight:650;font-variant-numeric:tabular-nums}
.quantity small{color:var(--tg-theme-hint-color);font-size:.78em;font-weight:400}
.empty{padding:1.1em .8em;text-align:center;color:var(--tg-theme-hint-color);font-size:.88em}
.pager{display:flex;align-items:center;gap:.6em;padding:0 1.25em}
.pager button{min-width:3em;min-height:3em;border:0;border-radius:.75em;background:var(--tg-theme-button-color);color:var(--tg-theme-button-text-color);font:inherit;font-size:.95em}
.pager button:disabled{background:var(--tg-theme-secondary-bg-color);color:var(--tg-theme-hint-color)}
.page-label{flex:1;text-align:center;color:var(--tg-theme-hint-color);font-size:.8em}
.note{margin:0;color:var(--tg-theme-subtitle-text-color);font-size:.78em;line-height:1.25}
@media(max-width:360px){.panel{gap:.65em}.metric{padding:.55em .6em}.row{padding:.42em .58em}}
</style>"""

_MARKUP = """<main class="panel">
<header class="heading"><span class="mark">▦</span><span><strong class="title">Склад</strong><br><span class="subtitle">Текущие остатки</span></span></header>
<section class="metrics"><div class="metric"><span class="metric-label">Позиций</span><strong class="metric-value" id="positions"></strong></div><div class="metric"><span class="metric-label">Всего единиц</span><strong class="metric-value" id="units"></strong></div></section>
<section><div class="section-head"><strong class="section-title">Товары</strong><span class="muted" id="shown"></span></div><div class="products" id="products"></div></section>
<nav class="pager" id="pager"><button id="prev" aria-label="Предыдущая страница">‹</button><span class="page-label" id="page"></span><button id="next" aria-label="Следующая страница">›</button></nav>
<p class="note" id="note"></p>
</main>"""

_SCRIPT_PREFIX = """<script>
const ITEMS=__ITEMS__;
const TOTAL=__TOTAL__;
const TOTAL_UNITS=__UNITS__;
const SIZE=__PAGE_SIZE__;
const $=id=>document.getElementById(id);
const pages=Math.max(1,Math.ceil(ITEMS.length/SIZE));
let page=0;
try{const saved=Number(localStorage.getItem('stock-page'));if(Number.isInteger(saved)&&saved>=0)page=Math.min(saved,pages-1)}catch{}
function draw(){
 const start=page*SIZE;
 const rows=ITEMS.slice(start,start+SIZE).map(item=>{const row=document.createElement('div');row.className='row';const name=document.createElement('span');name.className='name';name.textContent=item.n;const quantity=document.createElement('strong');quantity.className='quantity';quantity.textContent=new Intl.NumberFormat(navigator.language).format(item.q)+' ';const unit=document.createElement('small');unit.textContent='шт.';quantity.appendChild(unit);row.appendChild(name);row.appendChild(quantity);return row});
 $('products').replaceChildren(...rows);
 $('positions').textContent=new Intl.NumberFormat(navigator.language).format(TOTAL);
 $('units').textContent=new Intl.NumberFormat(navigator.language).format(TOTAL_UNITS);
 $('shown').textContent=!ITEMS.length&&TOTAL?'/list':ITEMS.length<TOTAL?'первые '+ITEMS.length+' из '+TOTAL:'';
 $('page').textContent=ITEMS.length?((start+1)+'–'+Math.min(start+SIZE,ITEMS.length)+' из '+ITEMS.length):'Список пуст';
 $('prev').disabled=page===0;$('next').disabled=page>=pages-1;$('pager').hidden=pages<=1;
 $('note').textContent=!ITEMS.length&&TOTAL?'Список доступен через /list':ITEMS.length<TOTAL?'Полный перечень: /list':(TOTAL?'Снимок на момент открытия':'Добавьте первый товар через меню');
 try{localStorage.setItem('stock-page',String(page))}catch{}
}
$('prev').addEventListener('click',()=>{if(page>0){page--;draw()}});
$('next').addEventListener('click',()=>{if(page<pages-1){page++;draw()}});
draw();
const TW=window.TelegramWidget;if(TW&&typeof TW.ready==='function')TW.ready();
</script>"""


def _script_json(value: object) -> str:
    """Encode JSON safe to embed in an inline script, including hostile names."""
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _build_html(products: list[dict], total: int, total_units: int) -> str:
    items = [{"n": str(product["display_name"]), "q": int(product["quantity"])} for product in products]
    script = (
        _SCRIPT_PREFIX.replace("__ITEMS__", _script_json(items))
        .replace("__TOTAL__", str(total))
        .replace("__UNITS__", str(total_units))
        .replace("__PAGE_SIZE__", str(PAGE_SIZE))
    )
    return _STYLE + _MARKUP + script


def render_stock_widget(products: list[dict]) -> str:
    """Build a compact, paged Bot API widget with a safe text-only data path."""
    total = len(products)
    total_units = sum(int(product["quantity"]) for product in products)
    count = min(total, MAX_PRODUCTS_IN_HTML)

    while count:
        document = _build_html(products[:count], total, total_units)
        encoded = document.encode("utf-8")
        compressed_size = len(zlib.compress(encoded, 9))
        if b"\0" not in encoded and len(encoded) <= 32_768 and compressed_size <= TARGET_COMPRESSED_BYTES:
            return document
        count -= 1

    document = _build_html([], total, total_units)
    encoded = document.encode("utf-8")
    if b"\0" in encoded or len(encoded) > 32_768 or len(zlib.compress(encoded, 9)) > 4_096:
        raise ValueError("Telegram widget HTML exceeds the Bot API size limit")
    return document


def stock_widget_caption(products: list[dict]) -> str:
    """Caption remains useful in chat lists and clients without widget support."""
    total_units = sum(int(product["quantity"]) for product in products)
    caption = f"Склад: {len(products)} позиций · {total_units} шт. Полный список: /list"
    return caption[:1024]
