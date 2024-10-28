import os
import logging
from sys import stdout
from dotenv import load_dotenv

from telegrambot import TelegramBot

def setup_logging() -> None:
    level = logging.DEBUG if os.getenv("DEV") == 'True' else logging.INFO

    logging.basicConfig(
        level=level,
        format="[%(asctime)s %(levelname)s][%(name)s] %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler("latest.log", "w", encoding="utf-8"),
            logging.StreamHandler(stdout)
        ]
    )

    # remove verbose logs from httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)

def main() -> None:
    load_dotenv()
    setup_logging()

    token = os.getenv('TOKEN')
    if not token:
        logging.error("Токен бота не найден в переменных окружения")
        return
    
    chat_id = int(os.getenv("DEVELOPER_CHAT_ID") or "0")

    try:
        bot = TelegramBot(token, chat_id)
        bot.run()
    except Exception as e:
        logging.exception(f"Произошла ошибка при запуске бота: {e}")
        raise e

if __name__ == '__main__':
    main()
