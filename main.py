import asyncio
import json
import logging
import os
import time
from pathlib import Path

import httpx
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiohttp import web

# ──────────────────────────────────────────────────────────────────────────
# КОНФИГ
# ──────────────────────────────────────────────────────────────────────────

# Токен теперь берём из переменной окружения, а не хардкодим в коде.
# Перед запуском: export BOT_TOKEN="твой_новый_токен_от_BotFather"
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Публичный https-адрес, на котором будет открываться веб-апп в Telegram.
# Telegram WebApp ОБЯЗАТЕЛЬНО требует https (localhost не подойдёт).
# Для теста можно поднять ngrok/cloudflared и вставить сюда выданный адрес,
# либо задеплоить на любой хостинг с доменом и SSL.
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://example.com")

# Порт, на котором будет слушать встроенный веб-сервер (отдаёт index.html и API)
WEB_PORT = int(os.getenv("PORT", "8080"))

# Если хотите, чтобы заказы дублировались в чат/группу администратора —
# впишите сюда chat_id (можно узнать у @userinfobot). Необязательно.
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

KORZINKA_CATEGORIES_URL = "https://catalog.korzinka.uz/api/catalogs/categories"

BASE_DIR = Path(__file__).parent
WEB_DIR = BASE_DIR / "web"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("korzinka_bot")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ──────────────────────────────────────────────────────────────────────────
# ПРОСТОЙ КЭШ ДАННЫХ КАТАЛОГА (чтобы не дёргать korzinka на каждый чих)
# ──────────────────────────────────────────────────────────────────────────

_cache = {"data": None, "ts": 0}
CACHE_TTL = 60 * 10  # 10 минут


def _format_price(price_str: str) -> int:
    """'16 990' -> 16990"""
    if not price_str:
        return 0
    return int(str(price_str).replace(" ", "").replace("\xa0", "") or 0)


async def fetch_catalog() -> list[dict]:
    """Тянем каталог у Корзинки, кэшируем, приводим к удобному плоскому виду."""
    now = time.time()
    if _cache["data"] is not None and now - _cache["ts"] < CACHE_TTL:
        return _cache["data"]

    async with httpx.AsyncClient(timeout=15.0, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }) as client:
        resp = await client.get(KORZINKA_CATEGORIES_URL)
        resp.raise_for_status()
        raw = resp.json()

    sections = []
    for section in raw.get("data", []):
        products = []
        for p in section.get("products", []):
            if p.get("is_banner"):
                continue
            prices = p.get("prices", {})
            products.append({
                "id": p.get("id"),
                "title": p.get("title_ru") or p.get("title") or "Товар",
                "price": _format_price(prices.get("actual_price")),
                "old_price": _format_price(prices.get("old_price")),
                "is_discount": bool(prices.get("is_discount")),
                "discount_label": prices.get("price_tag_title_ru") or "",
                "weight": p.get("weight_param") or "",
                "image": p.get("small_image_url") or "",
                "category_id": section.get("id"),
            })
        if not products:
            continue
        sections.append({
            "id": section.get("id"),
            "title": section.get("title_ru") or section.get("title_uz") or "Категория",
            "slug": section.get("slug"),
            "products": products,
        })

    _cache["data"] = sections
    _cache["ts"] = now
    return sections


# ──────────────────────────────────────────────────────────────────────────
# TELEGRAM BOT HANDLERS
# ──────────────────────────────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[
            types.KeyboardButton(
                text="🛒 Открыть магазин",
                web_app=types.WebAppInfo(url=WEBAPP_URL),
            )
        ]],
        resize_keyboard=True,
    )
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Это семейный магазин Корзинки прямо в Telegram.\n"
        "Нажми на кнопку ниже, чтобы открыть каталог и выбрать товары.",
        reply_markup=kb,
    )


@dp.message(F.web_app_data)
async def handle_webapp_order(message: types.Message):
    """Сюда прилетает корзина, когда пользователь жмёт 'Оформить заказ' в веб-аппе."""
    try:
        cart = json.loads(message.web_app_data.data)
    except (json.JSONDecodeError, AttributeError):
        await message.answer("⚠️ Не удалось прочитать заказ. Попробуй ещё раз.")
        return

    if not cart:
        await message.answer("Корзина пуста.")
        return

    lines = ["🧾 <b>Новый заказ:</b>\n"]
    total = 0
    for item in cart.values():
        subtotal = item["price"] * item["count"]
        total += subtotal
        lines.append(f"• {item['name']} × {item['count']} — {subtotal:,} сум".replace(",", " "))
    lines.append(f"\n<b>Итого: {total:,} сум</b>".replace(",", " "))

    text = "\n".join(lines)
    await message.answer(text, parse_mode="HTML")

    if ADMIN_CHAT_ID:
        try:
            user = message.from_user
            header = f"Заказ от {user.full_name} (@{user.username or user.id}):\n\n"
            await bot.send_message(ADMIN_CHAT_ID, header + text, parse_mode="HTML")
        except Exception as e:
            log.error("Не удалось отправить заказ админу: %s", e)


@dp.message(F.text)
async def handle_text(message: types.Message):
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[
            types.KeyboardButton(text="🛒 Открыть магазин", web_app=types.WebAppInfo(url=WEBAPP_URL))
        ]],
        resize_keyboard=True,
    )
    await message.answer("Нажми на кнопку, чтобы открыть каталог 👇", reply_markup=kb)


# ──────────────────────────────────────────────────────────────────────────
# ВЕБ-СЕРВЕР: отдаёт index.html и JSON API для веб-аппа
# ──────────────────────────────────────────────────────────────────────────

async def api_categories(request: web.Request):
    sections = await fetch_catalog()
    out = [{"id": s["id"], "title": s["title"], "slug": s["slug"]} for s in sections]
    return web.json_response(out)


async def api_products(request: web.Request):
    sections = await fetch_catalog()
    category_id = request.query.get("category_id")
    q = (request.query.get("q") or "").strip().lower()

    products = []
    for s in sections:
        if category_id and str(s["id"]) != str(category_id):
            continue
        products.extend(s["products"])

    if q:
        products = [p for p in products if q in p["title"].lower()]

    return web.json_response(products)


async def api_product_detail(request: web.Request):
    product_id = request.match_info.get("product_id")
    sections = await fetch_catalog()
    for s in sections:
        for p in s["products"]:
            if str(p["id"]) == str(product_id):
                return web.json_response(p)
    return web.json_response({"error": "not_found"}, status=404)


async def index(request: web.Request):
    return web.FileResponse(WEB_DIR / "index.html")


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/api/categories", api_categories)
    app.router.add_get("/api/products", api_products)
    app.router.add_get("/api/products/{product_id}", api_product_detail)
    app.router.add_static("/static/", WEB_DIR, name="static")
    return app


# ──────────────────────────────────────────────────────────────────────────
# ЗАПУСК: бот (polling) + веб-сервер параллельно
# ──────────────────────────────────────────────────────────────────────────

async def run_web_server():
    app = build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    log.info("Веб-сервер запущен на порту %s", WEB_PORT)
    # держим корутину живой
    await asyncio.Event().wait()


async def run_bot():
    log.info("Бот запущен, WEBAPP_URL=%s", WEBAPP_URL)
    await dp.start_polling(bot)


async def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "Не задан BOT_TOKEN. Запусти так:\n"
            '  export BOT_TOKEN="твой_токен"\n'
            "  export WEBAPP_URL=\"https://твой-домен\"\n"
            "  python main.py"
        )
    await asyncio.gather(run_bot(), run_web_server())


if __name__ == "__main__":
    asyncio.run(main())
