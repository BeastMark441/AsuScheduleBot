import os
import logging
from dotenv import load_dotenv

from telegrambot import TelegramBot

def setup_logging() -> None:
    level: logging._Level = logging.INFO
    if os.getenv("DEV") == 'True':
        level = logging.DEBUG

    logging.basicConfig(
        format='[%(asctime)s %(levelname)s][%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        filename='latest.log', encoding='utf-8',
        level=level
    )

    # removes spam
    logging.getLogger("httpx").setLevel(logging.WARNING)

def main() -> None:
    load_dotenv()
    setup_logging()

    token = os.getenv('TOKEN')
    assert token is not None

    bot = TelegramBot(token)
    bot.run()

if __name__ == '__main__':
    main()