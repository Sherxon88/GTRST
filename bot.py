"""
bot.py — G-TRUST GTR Asosiy Fayl
"""
import asyncio, logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN, ADMIN_IDS
from database import init_db
from middlewares.security import SecurityMiddleware, ContentFilterMiddleware
from handlers.start_handler import router as start_router
from handlers.kyc_handler   import router as kyc_router
from handlers.wifi_handler  import router as wifi_router
from handlers.ads_handler   import router as ads_router
from handlers.admin_handler import router as admin_router

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
log = logging.getLogger(__name__)

async def set_commands(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start",     description="🏠 Boshlash"),
        BotCommand(command="kyc",       description="🪪 KYC tasdiqlash"),
        BotCommand(command="admin",     description="👑 Admin panel"),
        BotCommand(command="broadcast", description="📣 Xabar yuborish"),
    ])

async def setup_scheduler(bot: Bot):
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from database import distribute_weekly_rewards
        scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
        scheduler.add_job(distribute_weekly_rewards, "cron",
                          day_of_week="mon", hour=10, minute=0, args=[bot])
        scheduler.start()
    except ImportError:
        pass

async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(SecurityMiddleware())
    dp.message.middleware(ContentFilterMiddleware())
    dp.include_router(start_router)
    dp.include_router(kyc_router)
    dp.include_router(wifi_router)
    dp.include_router(ads_router)
    dp.include_router(admin_router)
    await set_commands(bot)
    await setup_scheduler(bot)
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid,
                "🚀 *G-TRUST GTR Bot ishga tushdi!*",
                parse_mode="Markdown")
        except: pass
    log.info("🚀 Bot ishga tushdi!")
    await dp.start_polling(bot,
        allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
