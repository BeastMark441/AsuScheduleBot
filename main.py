import os
import logging
from sys import stdout
from dotenv import load_dotenv

from telegrambot import TelegramBot

def setup_logging() -> None:
    level: logging._Level = logging.INFO
    if os.getenv("DEV") == 'True':
        level = logging.DEBUG

    rootLogger = logging.getLogger("")

    rootLogger.setLevel(level)

    fileFormatter = logging.Formatter("[%(asctime)s %(levelname)s][%(name)s] %(message)s", datefmt='%Y-%m-%d %H:%M:%S')
    fileHandler = logging.FileHandler("latest.log", "w", encoding="utf-8")
    fileHandler.setFormatter(fileFormatter)

    rootLogger.addHandler(fileHandler)

    consoleFormatter = logging.Formatter("[%(asctime)s %(levelname)s][%(name)s] %(message)s", datefmt="%H:%M:%S")
    consoleHandler = logging.StreamHandler(stdout)
    consoleHandler.setFormatter(consoleFormatter)

    rootLogger.addHandler(consoleHandler)

    rootLogger.setLevel(level)

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