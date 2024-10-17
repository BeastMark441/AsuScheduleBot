import os
import logging
from dotenv import load_dotenv

from telegrambot import TelegramBot

def setup_logging():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

def main() -> None:
    load_dotenv()
    setup_logging()

    token = os.getenv('TOKEN')
    assert token is not None

    bot = TelegramBot(token)
    bot.run()

if __name__ == '__main__':
    main()