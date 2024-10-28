import logging
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import Update  # Добавляем импорт Update
from datetime import timedelta

from asu import schedule
from .commands import (
    start_callback, 
    schedule_callback, 
    cleansavegroup_callback,
    cleansavelect_callback,
    GET_GROUP_NAME,
    SHOW_SCHEDULE,
    SAVE_GROUP,
    get_group_name,
    save_group_callback,
    handle_show_schedule,
    # Импортируем все необходимые компоненты для lecturer_handler
    GET_LECTURER_NAME,
    SHOW_LECTURER_SCHEDULE,
    SAVE_LECTURER,
    CHOOSE_SCHEDULE_TYPE,  # Добавляем новое состояние
    lecturer_callback,
    get_lecturer_name,
    save_lecturer_callback,
    cancel_schedule,
    handle_schedule_choice,  # Добавляем новые обработчики
    schedule_handler,  # Импортируем готовые обработчики
    lecturer_handler
)
from .database import Database

class TelegramBot():
    def __init__(self, token: str):
        if not token:
            raise ValueError("Токен бота не может быть пустым")
        self.token = token
        self.db = Database()

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

        application.run_polling(allowed_updates=Update.ALL_TYPES)

        logging.info("Бот запущен")

    def __del__(self):
        self.db.close()
