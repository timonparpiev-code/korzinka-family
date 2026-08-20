import os
import asyncio
import logging
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

BOT_TOKEN = os.getenv("BOT_TOKEN")

# СЮДА ВСТАВЬ СВОЮ ССЫЛКУ С GITHUB PAGES (из вкладки Pages)
WEB_APP_URL = "WEB_APP_URL = "https://timonparpiev-code.github.io/korzinka-family/?v=2""

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Открыть каталог Корзинки", web_app=WebAppInfo(url=WEB_APP_URL))]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Нажми на кнопку ниже, чтобы открыть семейный каталог!",
        reply_markup=kb
    )

@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    data = json.loads(message.web_app_data.data)
    
    order_text = "🛍 **Новый семейный заказ:**\n\n"
    total_sum = 0
    
    for item_id, item in data.items():
        item_sum = item['price'] * item['count']
        total_sum += item_sum
        order_text += f"• {item['name']} x{item['count']} = {item_sum:,} сум\n"
        
    order_text += f"\n💰 **Итого:** {total_sum:,} сум"
    
    await message.answer(order_text, parse_mode="Markdown")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
