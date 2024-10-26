import logging
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from datetime import timedelta

from asu import schedule
from .commands import *
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

        schedule_handler = ConversationHandler(
            entry_points=[CommandHandler("schedule", schedule_callback)],
            states={
                GET_GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group_name)],
                SAVE_GROUP: [CallbackQueryHandler(save_group_callback, pattern='^save_yes|save_no$')],
                SHOW_SCHEDULE: [CallbackQueryHandler(handle_show_schedule, pattern='^T|M|W|NW$')],
            },
            fallbacks=[],
            per_message=False,
            name="schedule_conversation"
        )
        
        application.add_handler(schedule_handler)
        application.add_handler(CommandHandler("start", start_callback))
        application.add_handler(CommandHandler("cleansavegroup", cleansavegroup_callback))

        application.run_polling(allowed_updates=Update.ALL_TYPES)

        logging.info("Бот запущен")

    def __del__(self):
        self.db.close()
