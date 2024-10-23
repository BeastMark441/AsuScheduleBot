import logging
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters

from asu import schedule

from .commands import *

class TelegramBot():
    def __init__(self, token: str):
        assert token

        self.token = token
        

    def run(self):
        builder = Application.builder()

        builder.token(self.token)

        application = builder.build()

        schedule_handler = ConversationHandler(
            entry_points=[CommandHandler("schedule", schedule_callback)],
            states={
                GET_GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group_name)],
                SHOW_SCHEDULE: [CallbackQueryHandler(handle_show_schedule, '^T|M|W$')],
            },
            fallbacks=[],
            conversation_timeout=timedelta(seconds=30)
        )
        application.add_handler(schedule_handler)
        application.add_handler(CommandHandler("start", start_callback))

        application.run_polling(allowed_updates=Update.ALL_TYPES)