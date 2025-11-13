import os
import ssl
import io
import base64
import aiohttp
import dns.resolver
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types, Router
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from PIL import Image

# ---------- DNS-OVERRIDE (помогает на Render) ----------
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ['8.8.8.8', '8.8.4.4']

# ---------- ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ----------
CLIENT_ID     = os.getenv("CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
BOT_TOKEN     = os.getenv("BOT_TOKEN", "")
WORKER_URL    = os.getenv("WORKER_URL", "https://sneakercard.onrender.com")
# Тестовый флаг: поставить INSECURE_SSL=1 в Render для отключения проверки SSL (только для тестов!)
INSECURE_SSL  = os.getenv("INSECURE_SSL", "0") == "1"

AUTH_BASIC = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()

# ---------- Инициализация бота и диспетчера ----------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ---------- SSL-контекст ----------
def make_ssl_context():
    if INSECURE_SSL:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    else:
        return ssl.create_default_context()

# ---------- ПОЛУЧАЕМ ACCESS-TOKEN ----------
async def get_token(session):
    url  = "https://gigachat.devices.sberbank.ru/api/v2/oauth"
    headers = {
        "Authorization": f"Basic {AUTH_BASIC}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    async with session.post(url, headers=headers, data="scope=GIGACHAT_API_PERS") as resp:
        j = await resp.json()
        return j.get("access_token")

# ---------- KANDINSKY 3 (редактирование изображения) ----------
async def kandinsky(session, base64_img: str, token: str):
    url  = "https://gigachat.devices.sberbank.ru/api/v1/images/edit"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "image": base64_img,
        "prompt": "white studio, soft light, slight shadow, no watermark",
        "model": "kandinsky-3.0"
    }
    async with session.post(url, headers=headers, json=payload) as r:
        j = await r.json()
        return j.get("image")

# ---------- ХЕНДЛЕР ПРИЁМА ФОТО ----------
@router.message(F.photo)
async def get_photo(msg: types.Message):
    try:
        file = await bot.get_file(msg.photo[-1].file_id)
        b_io = await bot.download_file(file.file_path)
    except Exception:
        await msg.answer("Не удалось получить файл у Telegram. Попробуйте ещё раз.")
        return

    img_b64 = base64.b64encode(b_io.getvalue()).decode()
    ssl_context = make_ssl_context()
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            token = await get_token(session)
        except Exception:
            await msg.answer("Ошибка при получении токена (network/SSL).")
            return

        if not token:
            await msg.answer("Ошибка авторизации — не получили access token.")
            return

        try:
            new_b64 = await kandinsky(session, img_b64, token)
        except Exception:
            await msg.answer("Ошибка при обращении к API генерации изображения.")
            return

        if new_b64:
            Image.open(io.BytesIO(base64.b64decode(new_b64))).save("/tmp/card.jpg")
            await msg.answer_photo(
                FSInputFile("/tmp/card.jpg"),
                caption="✅ Готово! 1024×1024, без водяных знаков.",
                reply_markup=ikb_webhook()
            )
        else:
            await msg.answer("😞 Попробуйте ещё раз.")

# ---------- КНОПКИ + ПЛАТЁЖИ ----------
def ikb_webhook():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="10 шт – 199 ⭐", pay=True)]
    ])

@router.pre_checkout_query()
async def pre_check(p: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(p.id, ok=True)

@router.message(F.successful_payment)
async def paid(msg: types.Message):
    await msg.answer("Спасибо! ZIP с 10 шаблонами – заглушка)")

# ---------- HTTP-ENDPOINTS ----------
async def on_startup(app: web.Application):
    await bot.set_webhook(f"{WORKER_URL}/webhook")

async def on_shutdown(app: web.Application):
    try:
        await bot.delete_webhook()
    except Exception:
        pass

async def handle_ping(request: web.Request):
    return web.Response(text="pong")

def create_app() -> web.Application:
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
    app.router.add_get("/ping", handle_ping)
    return app

# ---------- ЗАПУСК ----------
if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=8080)
