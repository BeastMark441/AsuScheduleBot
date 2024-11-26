import html
import json
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, CommandHandler

from settings import Settings
from telegrambot.commands import *
from telegrambot.context import ApplicationContext, context_types

settings = Settings() # pyright: ignore[reportCallIssue]

# pyright: reportUnknownMemberType=false
async def on_post_init(application: Application): # pyright: ignore[reportMissingTypeArgument, reportUnknownParameterType]
    application.bot_data._settings = settings

    application.add_handler(CommandHandler("start", start_callback))
    application.add_handler(CommandHandler("cleansavegroup", cleansavegroup_callback))
    application.add_handler(CommandHandler("cleansavelect", cleansavelect_callback))

    application.add_handler(schedule_handler)
    application.add_handler(lecturer_handler)
    application.add_handler(notes_handler)
    
    application.add_error_handler(error_handler)
    
async def disabled_command_handler(update: Update, _context: ApplicationContext) -> None:
    await update.message.reply_text("Данная команда была отключена")

async def error_handler(update: object, context: ApplicationContext) -> None:
    # If exception happended in message update, then notify about the error to the user
    if isinstance(update, Update) and (message := update.message):
        await message.reply_text("Произошла ошибка. Пожалуйста, попробуйте еще раз позже или свяжитесь с поддержкой.")
    
    # Log the error before we do anything else, so we can see it even if something breaks.
    logging.error("Exception while handling an update:", exc_info=context.error)
    
    if not (dev_chat_id := context.settings.DEVELOPER_CHAT_ID):
        return

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
        chat_id=dev_chat_id, text=message, parse_mode=ParseMode.HTML
    )
    
    
application = (
    ApplicationBuilder()
    .token(settings.BOT_TOKEN)
    # Processing updates concurrently is not recommended when stateful handlers like telegram.ext.ConversationHandler are used.
    # https://docs.python-telegram-bot.org/en/latest/telegram.ext.applicationbuilder.html#telegram.ext.ApplicationBuilder.concurrent_updates
    .concurrent_updates(False)
    .post_init(on_post_init)
    .context_types(context_types)
    .build()
)
