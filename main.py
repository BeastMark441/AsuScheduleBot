import asyncio
import logging
import logging.handlers
import os
from sys import stdout

from dotenv import load_dotenv

from database import db
from telegrambot.bot import application

def setup_logging() -> None:
    level = logging.INFO

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

def main() -> None:
    load_dotenv()
    setup_logging()
    
    loop = asyncio.new_event_loop()
    loop.run_until_complete(setup_database())
    
    application.run_polling(drop_pending_updates=True)
    

if __name__ == '__main__':
    main()