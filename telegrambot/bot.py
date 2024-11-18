import asyncio
import html
import json
import logging
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

from .commands import *

class TelegramBot():
    def __init__(self, token: str, dev_chat_id: int):
        if not token:
            raise ValueError("Токен бота не может быть пустым")
        self.token: str = token
        self.developer_chat_id: int = dev_chat_id
        self.application = None

    async def run(self):
        application = self.application = (
            Application.builder()
            .token(self.token)
            # Processing updates concurrently is not recommended when stateful handlers like telegram.ext.ConversationHandler are used.
            # https://docs.python-telegram-bot.org/en/latest/telegram.ext.applicationbuilder.html#telegram.ext.ApplicationBuilder.concurrent_updates
            .concurrent_updates(False)
            .build()
        )
        
        # Используем импортированные обработчики вместо их определения здесь
        application.add_handler(schedule_handler)
        application.add_handler(lecturer_handler)
        application.add_handler(CommandHandler("start", start_callback))
        application.add_handler(CommandHandler("cleansavegroup", cleansavegroup_callback))
        application.add_handler(CommandHandler("cleansavelect", cleansavelect_callback))
        
        application.bot_data['DEVELOPER_CHAT_ID'] = self.developer_chat_id
        application.add_error_handler(error_handler)
        
        allowed_updates = [Update.MESSAGE, Update.CALLBACK_QUERY]
        
        def error_callback(exc: TelegramError) -> None:
            application.create_task(self.application.process_error(error=exc, update=None))
        
        await application.initialize()
        await application.updater.start_polling(allowed_updates=allowed_updates, drop_pending_updates=True, error_callback=error_callback)
        await application.start()
        
    async def stop(self):
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Log the error before we do anything else, so we can see it even if something breaks.
    logging.error("Exception while handling an update:", exc_info=context.error)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        "An exception was raised while handling an update\nSee latest.log to get trace back\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>user_data = {html.escape(str(context.user_data))}</pre>\n\n"
    )

    # Finally, send the message
    await context.bot.send_message(
        chat_id=context.application.bot_data['DEVELOPER_CHAT_ID'], text=message, parse_mode=ParseMode.HTML
    )