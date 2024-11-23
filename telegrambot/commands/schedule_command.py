from datetime import timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters

import asu
from database.models import Group, SearchType
from telegrambot.context import ApplicationContext

from .common import *

async def schedule_callback(update: Update, context: ApplicationContext) -> int:
    """Обработчик команды /schedule"""
    
    # If user enters group name after the command, then search for it
    # If no input, then use saved, otherwise ask user to enter group
    
    group_name = ''.join(context.args) if context.args else ""
    if group_name:
        
        return await handle_schedule_by_name(update, context, group_name)
    
    group = await get_saved_group(update.effective_user)
    if group:
        await add_statistics(update.effective_user, SearchType.group, group.name)
        
        context.user_data.selected_schedule = group
        return await show_schedule_options(update, context)
    
    await update.message.reply_text("Введите название группы:")
    return GET_GROUP_NAME

async def get_group_name(update: Update, context: ApplicationContext) -> int:
    """Обработчик ввода названия группы"""
    
    if not (group_name := update.message.text):
        return END
    
    if not group_name:
        await update.message.reply_text("Пожалуйста, введите корректное название группы")
        return GET_GROUP_NAME
    
    return await handle_schedule_by_name(update, context, group_name)

async def handle_schedule_by_name(update: Update, context: ApplicationContext, group_name: str) -> int:
    """Основной обработчик запроса расписания"""
    
    # Limit group name to 50 symbols
    group_name = group_name.strip()[:50]
    
    # Stats
    await add_statistics(update.effective_user, SearchType.group, group_name)
    
    schedule = await asu.client.search_group(group_name)
    if not schedule:
        await update.message.reply_text("Ошибка получения группы. Пожалуйста, проверьте название и попробуйте снова")
        return END
    
    context.user_data.selected_schedule = schedule
    
    if not (saved_group := await get_saved_group(update.effective_user)) \
        or saved_group.group_id != schedule.group_id:
            # Checking by group id might be bad idea?
            return await _ask_to_save_group(update, context, schedule.name)
    
    return await show_schedule_options(update, context)

async def _ask_to_save_group(update: Update, _context: ApplicationContext, group_name: str) -> int:
    """Запрос на сохранение группы"""
    keyboard = [
        [InlineKeyboardButton("Да", callback_data="save_yes"),
         InlineKeyboardButton("Нет", callback_data="save_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Хотите ли вы сохранить группу {group_name} для быстрого доступа в будущем?",
        reply_markup=reply_markup)
    return SAVE_GROUP

async def save_group_callback(update: Update, context: ApplicationContext) -> int:
    """Обработчик ответа на запрос сохранения группы"""
    if not (query := update.callback_query):
        return END
    
    await query.answer()

    if query.data == "save_yes":
        schedule = context.user_data.selected_schedule
        if isinstance(schedule, Group):
            await set_saved_group(update.effective_user, schedule)
            await query.edit_message_text(f"Группа {schedule.name} сохранена.")
        else:
            await query.edit_message_text("Произошла ошибка при сохранении группы.")

    return await show_schedule_options(update, context)

async def show_schedule_options(update: Update, context: ApplicationContext) -> int:
    """Показать опции выбора периода расписания"""

    keyboard = [
        [InlineKeyboardButton("Сегодня", callback_data="T")],
        [InlineKeyboardButton("Завтра", callback_data="M")],
        [InlineKeyboardButton("На эту неделю", callback_data="W")],
        [InlineKeyboardButton("На следующую неделю", callback_data="NW")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    schedule = context.user_data.selected_schedule
    await update.effective_message.reply_text(
            f"📚 Группа {schedule.name}\nВыберите, на какой день хотите получить расписание:",
            reply_markup=reply_markup)
    
    return SHOW_SCHEDULE
        
schedule_handler = ConversationHandler(
    entry_points=[
        CommandHandler("schedule", schedule_callback),
    ],
    states={
        GET_GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group_name)],
        SAVE_GROUP: [CallbackQueryHandler(save_group_callback, pattern='^save_yes|save_no$')],
        SHOW_SCHEDULE: [
            CallbackQueryHandler(handle_show_schedule, pattern='^T|M|W|NW$')
        ]
    },
    fallbacks=[MessageHandler(filters.COMMAND, exit_conversation)],
    allow_reentry=True,
    # https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-Asked-Questions#what-do-the-per_-settings-in-conversationhandler-do
    per_message=False,
    per_user=False,
    conversation_timeout=timedelta(seconds=30),
    name="schedule_conversation"
)