import logging
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters

from .commandHandlers import *

class TelegramBot():
    def __init__(self, token: str):
        assert token

        self.token = token
        

    def run(self):
        builder = Application.builder()

        builder.token(self.token)

        application = builder.build()

        application.add_handler(CommandHandler("start", start_callback))
        application.add_handler(CommandHandler("schedule", schedule_callback))
        application.add_handler(CallbackQueryHandler(button_callback))

        application.run_polling(allowed_updates=Update.ALL_TYPES)