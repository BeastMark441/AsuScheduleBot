from importlib.metadata import entry_points
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from .commands import *

class TelegramBot():
    def __init__(self, token: str) -> None:
        assert token

        self.token: str = token

    def run(self) -> None:
        builder = ApplicationBuilder()
        builder.token(self.token)
        application = builder.build()

        schedule_conv = ConversationHandler(
            entry_points=[CommandHandler("schedule", schedule_callback)],
            states={
                GET_GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group_callback)]
            },
            fallbacks=[]
        )
        
        application.add_handler(schedule_conv)
        application.add_handler(CommandHandler("start", start_callback))

        application.run_polling()
