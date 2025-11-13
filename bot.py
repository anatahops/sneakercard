import os, asyncio, base64, aiohttp, io
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image

# Получаем переменные окружения из Hugging Face Spaces
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
BOT_TOKEN = os.getenv("BOT_TOKEN")
AUTH_BASIC = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# 1. Получаем access_token (30 мин)
async def get_token(session):
    url = "https://gigachat.devices.sberbank.ru/api/v2/oauth"
    headers = {"Authorization": f"Basic {AUTH_BASIC}",
               "Content-Type": "application/x-www-form-urlencoded"}
    async with session.post(url, headers=headers, data="scope=GIGACHAT_API_PERS") as resp:
        return (await resp.json()).get("access_token")

# 2. Kandinsky 3
async def kandinsky(base64_img: str, token: str):
    url = "https://gigachat.devices.sberbank.ru/api/v1/images/edit"
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json"}
    payload = {"image": base64_img,
               "prompt": "white studio, soft light, slight shadow, no watermark",
               "model": "kandinsky-3.0"}
    async with aiohttp.ClientSession() as s:
        async with s.post(url, headers=headers, json=payload) as r:
            return (await r.json()).get("image")

# 3. Приём фото
@dp.message(F.photo)
async def get_photo(msg: types.Message):
    file = await bot.get_file(msg.photo[-1].file_id)
    b_io = await bot.download_file(file.file_path)
    img_b64 = base64.b64encode(b_io.getvalue()).decode()

    async with aiohttp.ClientSession() as session:
        token = await get_token(session)
        if not token:
            await msg.answer("Ошибка авторизации")
            return
        new_b64 = await kandinsky(img_b64, token)
        if new_b64:
            Image.open(io.BytesIO(base64.b64decode(new_b64))).save("/tmp/card.jpg")
            await msg.answer_photo(
                FSInputFile("/tmp/card.jpg"),
                caption="✅ Готово! 1024×1024, без водяных знаков.",
                reply_markup=ikb_buy()
            )
        else:
            await msg.answer("😞 Попробуйте ещё раз.")

# 4. Кнопки + Stars
def ikb_buy():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="10 шт – 199 ⭐", pay=True)]
    ])

@dp.pre_checkout_query()
async def pre_check(p: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(p.id, ok=True)

@dp.message(F.successful_payment)
async def paid(msg: types.Message):
    await msg.answer("Спасибо! ZIP с 10 шаблонами – заглушка)")

# 5. Запуск
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))