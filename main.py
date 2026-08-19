import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
import httpx

# Вставь сюда свой НОВЫЙ токен от @BotFather
BOT_TOKEN = "8683847303:AAEqvUFZdXS-7VZpjtbi-r9Gwd1wZQfjZ5o"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Функция поиска товаров через API
async def search_korzinka(query: str):
    url = f"https://api.korzinka.uz/search/?q={query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=10.0)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logging.error(f"Ошибка запроса к API: {e}")
    return None

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n"
        "Я семейный бот для заказов из Корзинки.\n\n"
        "Просто напиши мне название товара (например, *молоко* или *хлеб*), и я найду его!",
        parse_mode="Markdown"
    )

@dp.message(F.text)
async def handle_search(message: types.Message):
    query = message.text.strip()
    await message.answer(f"🔍 Ищу *«{query}»* в Корзинке...", parse_mode="Markdown")
    
    data = await search_korzinka(query)
    
    if not data:
        await message.answer("❌ Не удалось получить данные от сервера Korzinka.")
        return

    # Логируем ответ в консоль
    print("Полученный ответ от API:", data)
    
    await message.answer("Результат получен! Проверь консоль программы.")

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())