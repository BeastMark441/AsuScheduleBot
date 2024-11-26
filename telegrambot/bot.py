import html
import json
import logging
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue
from telegram.constants import ParseMode
from datetime import time as datetime_time

from .commands import *
from database.mariadb import MariaDB
from config.database import MARIADB_CONFIG

class TelegramBot():
    def __init__(self, token: str, dev_chat_id: int):
        if not token:
            raise ValueError("Токен бота не может быть пустым")
        self.token: str = token
        self.developer_chat_id: int = dev_chat_id
        self.db = MariaDB(**MARIADB_CONFIG)
        self._error_count = 0
        self._error_threshold = 10
        self._error_reset_time = time.time()

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
        
        # Добавляем обработчик статистики
        application.add_handler(stats_handler)
        
        application.bot_data['DEVELOPER_CHAT_ID'] = self.developer_chat_id
        application.add_error_handler(error_handler)

        # Задачи
        if application.job_queue:
            application.job_queue.run_daily(
                cleanup_notes,
                time=datetime_time(0, 0),
                days=(0, 1, 2, 3, 4, 5, 6)
            )
            application.job_queue.run_daily(
                self._cleanup_cache,
                time=datetime_time(hour=3, minute=0)
            )
            application.job_queue.run_daily(
                self._aggregate_statistics,
                time=datetime_time(hour=0, minute=5)
            )

        application.run_polling(allowed_updates=Update.ALL_TYPES)
        logging.info("Бот запущен")

    async def _cleanup_cache(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Очистка устаревшего кеша"""
        try:
            self.db.cleanup_cache()
            logging.info("Cache cleanup completed")
        except Exception as e:
            logging.error(f"Cache cleanup failed: {e}")

    async def _aggregate_statistics(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Агрегация статистики за предыдущий день"""
        try:
            self.db.aggregate_daily_statistics()
            logging.info("Daily statistics aggregation completed")
        except Exception as e:
            logging.error(f"Statistics aggregation failed: {e}")

    async def _handle_error(self, update: Update, error: Exception) -> None:
        """Улучшенная обработка ошибок"""
        now = time.time()
        if now - self._error_reset_time > 3600:  # Сброс счетчика каждый час
            self._error_count = 0
            self._error_reset_time = now
            
        self._error_count += 1
        
        if self._error_count > self._error_threshold:
            # Отправляем уведомление разработчикам о большом количестве ошибок
            await self.notify_developers(
                f"⚠️ Превышен порог ошибок ({self._error_threshold})\n"
                f"Последняя ошибка: {str(error)}"
            )
            self._error_count = 0

    async def notify_developers(self, message: str) -> None:
        """Отправка уведомления разработчикам"""
        try:
            if not self.developer_chat_id:
                return
                
            await self.application.bot.send_message(
                chat_id=self.developer_chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logging.error(f"Failed to notify developers: {e}")

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