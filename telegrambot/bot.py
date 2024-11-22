import html
import json
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue
from telegram.constants import ParseMode
from datetime import time

from .commands import *

class TelegramBot():
    def __init__(self, token: str, dev_chat_id: int):
        if not token:
            raise ValueError("Токен бота не может быть пустым")
        self.token: str = token
        self.developer_chat_id: int = dev_chat_id

    def run(self):
        application = (
            Application.builder()
            .token(self.token)
            .concurrent_updates(False)
            .build()
        )

        # Базовые команды
        application.add_handler(CommandHandler("start", start_callback))
        application.add_handler(CommandHandler("cleansavegroup", cleansavegroup_callback))
        application.add_handler(CommandHandler("cleansavelect", cleansavelect_callback))

        # Основные обработчики
        application.add_handler(schedule_handler)
        application.add_handler(lecturer_handler)
        application.add_handler(card_handler)
        application.add_handler(report_handler)
        application.add_handler(notes_handler)
        
        # Административные команды
        application.add_handler(admin_handler)
        application.add_handler(send_to_handler)
        application.add_handler(admin_report_callback)
        application.add_handler(unblock_handler)
        application.add_handler(broadcast_handler)
        
        application.bot_data['DEVELOPER_CHAT_ID'] = self.developer_chat_id
        application.add_error_handler(error_handler)

        # Задачи
        if application.job_queue:
            application.job_queue.run_daily(
                cleanup_notes,
                time=time(0, 0),
                days=(0, 1, 2, 3, 4, 5, 6)
            )

        application.run_polling(allowed_updates=Update.ALL_TYPES)
        logging.info("Бот запущен")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error("Exception while handling an update:", exc_info=context.error)

    # Ограничиваем размер сообщения
    def truncate_string(s: str, max_length: int = 1000) -> str:
        return s[:max_length] + "..." if len(s) > max_length else s

    try:
        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        message = (
            "An exception was raised while handling an update\n"
            f"<pre>{html.escape(truncate_string(json.dumps(update_str, indent=2, ensure_ascii=False)))}</pre>\n"
            f"<pre>chat_data = {html.escape(truncate_string(str(context.chat_data)))}</pre>\n"
            f"<pre>user_data = {html.escape(truncate_string(str(context.user_data)))}</pre>\n"
        )

        await context.bot.send_message(
            chat_id=context.application.bot_data['DEVELOPER_CHAT_ID'],
            text=message,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logging.error(f"Failed to send error message: {e}")