import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from config import BOT_TOKEN, MAX_TOKEN
import database

# Initialize bots and dispatchers
bot = None
dp = None
if BOT_TOKEN:
    try:
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher()
        print("Telegram bot initialized successfully.")
    except Exception as e:
        print(f"Telegram token is invalid or not working: {e}")
        bot = None
        dp = None

max_bot = None
max_dp = None
if MAX_TOKEN:
    try:
        max_bot = Bot(token=MAX_TOKEN)
        max_dp = Dispatcher()
        print("MAX bot initialized successfully.")
    except Exception as e:
        print(f"MAX token is invalid or not working: {e}")
        max_bot = None
        max_dp = None

# Telegram handlers
if dp:
    @dp.message(Command("start"))
    async def start(message: types.Message):
        await message.answer(
            "Привет!\n"
            "Отправь код подтверждения с сайта для привязки аккаунта."
        )

    @dp.message()
    async def confirm_code(message: types.Message):
        code = message.text.strip()
        user_id = database.link_telegram(code, message.from_user.id)
        if user_id:
            await message.answer("✅ Аккаунт успешно привязан к Telegram!")
        else:
            await message.answer("❌ Код не найден или уже использован.")

# MAX handlers
if max_dp:
    @max_dp.message(Command("start"))
    async def max_start(message: types.Message):
        await message.answer(
            "Привет! Это MAX бот.\n"
            "Отправь код подтверждения с сайта для привязки аккаунта."
        )

    @max_dp.message()
    async def max_confirm_code(message: types.Message):
        code = message.text.strip()
        user_id = database.link_max(code, message.from_user.id)
        if user_id:
            await message.answer("✅ Аккаунт успешно привязан к MAX!")
        else:
            await message.answer("❌ Код не найден или уже использован.")

async def main():
    tasks = []
    if dp and bot:
        tasks.append(dp.start_polling(bot))
    if max_dp and max_bot:
        tasks.append(max_dp.start_polling(max_bot))
    if tasks:
        print("Bot(s) started successfully.")
        await asyncio.gather(*tasks)
    else:
        print("No valid tokens found. Set BOT_TOKEN and/or MAX_TOKEN in .env file.")

if __name__ == "__main__":
    asyncio.run(main())