import logging
import logging.handlers
import os
import asyncio
from signal import SIGABRT, SIGINT, SIGTERM
from sys import stdout

from dotenv import load_dotenv

from telegrambot import TelegramBot

from database import db

def setup_logging() -> None:
    level = logging.DEBUG if os.getenv("DEV") == 'True' else logging.INFO

    os.makedirs("logs", exist_ok=True)

    file_handler = logging.handlers.TimedRotatingFileHandler("logs/latest.log", "midnight", backupCount=3, encoding="utf-8")

    logging.basicConfig(
        level=level,
        format="[%(asctime)s %(levelname)s][%(name)s] %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            file_handler,
            logging.StreamHandler(stdout)
        ]
    )

    # remove verbose logs from httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
async def setup_database():
    await db.run_migrations()

async def main() -> None:
    load_dotenv()
    setup_logging()
    await setup_database()

    token = os.getenv('TOKEN')
    if not token:
        logging.error("Токен бота не найден в переменных окружения")
        return
    
    chat_id = int(os.getenv("DEVELOPER_CHAT_ID") or "0")

    bot = TelegramBot(token, chat_id)
    await bot.run()
    
    try:
        await asyncio.Future() # sleeps forever
    except asyncio.CancelledError:
        await bot.stop()
        

def raise_system_exit():
    raise SystemExit

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    main_task = asyncio.ensure_future(main())
    for signal in [SIGINT, SIGTERM, SIGABRT]:
        try:
            loop.add_signal_handler(signal, raise_system_exit)
        except:
            pass

    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        main_task.cancel()
        loop.run_until_complete(main_task)
        loop.stop()
        
