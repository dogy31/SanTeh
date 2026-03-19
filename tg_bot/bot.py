import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from config import BOT_TOKEN
import database

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Привет!\n"
        "Отправь код подтверждения с сайта."
    )


@dp.message()
async def confirm_code(message: types.Message):

    code = message.text.strip()

    database.link_telegram(code, message.from_user.id)

    await message.answer(
        "✅ Аккаунт успешно привязан!"
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())