import html
import json
import logging
import traceback
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode
from telegram import Update  # Добавляем импорт Update

from .commands import *
from .database import Database

DEVELOPER_CHAT_ID: int = 0

class TelegramBot():
    def __init__(self, token: str, dev_chat_id: int):
        if not token:
            raise ValueError("Токен бота не может быть пустым")
        self.token = token
        self.db = Database()
        self.dev_chat_id = dev_chat_id

    def run(self):
        application = (
            Application.builder()
            .token(self.token)
            .build()
        )

        # Добавляем базу данных в пользовательские данные приложения
        application.bot_data['db'] = self.db

        # Используем импортированные обработчики вместо их определения здесь
        application.add_handler(schedule_handler)
        application.add_handler(lecturer_handler)
        application.add_handler(CommandHandler("start", start_callback))
        application.add_handler(CommandHandler("cleansavegroup", cleansavegroup_callback))
        application.add_handler(CommandHandler("cleansavelect", cleansavelect_callback))

        if self.dev_chat_id != 0:
            global DEVELOPER_CHAT_ID
            DEVELOPER_CHAT_ID = self.dev_chat_id
            application.add_error_handler(error_handler)

        application.run_polling(allowed_updates=Update.ALL_TYPES)

        logging.info("Бот запущен")

    def __del__(self):
        self.db.close()

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    global DEVELOPER_CHAT_ID

    # Log the error before we do anything else, so we can see it even if something breaks.
    logging.error("Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        "An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Finally, send the message
    await context.bot.send_message(
        chat_id=DEVELOPER_CHAT_ID, text=message, parse_mode=ParseMode.HTML
    )