import asyncio
from datetime import datetime, timedelta
from optparse import Option
import re
from tarfile import data_filter
from typing import Optional, Union
import telegram
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, ConversationHandler
import asu
from asu import Schedule

END = ConversationHandler.END
GET_GROUP_NAME, SHOW_SCHEDULE = range(2)

SELECTED_SCHEDULE = 'schedule'

async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command"""
    user = update.effective_user
    await update.message.reply_html(
        f"Привет, {user.mention_html()}! Это бот для поиска расписания студентов и преподавателей АлтГУ.\n"
            "Используй контекстное меню или команды для взаимодействия с ботом.\n"
            "Если возникли ошибки или есть идеи, напиши нам.\n"
            "Контакты в описании бота")
    

async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Schedule command"""
    if context.args is None or len(context.args) == 0:
        await update.message.reply_text("Введите название группы:")
        return GET_GROUP_NAME
    
    group_name = ''.join(context.args)
    return await handle_schedule(update, context, group_name)

async def get_group_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    group_name = update.message.text

    if not group_name:
        return END

    return await handle_schedule(update, context, group_name)

async def handle_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, group_name: str) -> int:
    schedule = await find_schedule_of_group(group_name)
    if not schedule:
        await update.message.reply_text("Ошибка получения группы")
        return END
    
    context.user_data[SELECTED_SCHEDULE] = schedule # type: ignore
    
    # Show keyboard to select time
    keyboard = [
        [InlineKeyboardButton("Сегодня", callback_data="T")],
        [InlineKeyboardButton("Завтра", callback_data="M")],
        [InlineKeyboardButton("На всю неделю", callback_data="W")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(f"📚 Группа {schedule.name}\nВыберите, на какой день хотите получить расписание:", reply_markup=reply_markup)
    return SHOW_SCHEDULE

async def handle_show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer() # type: ignore

    options: dict[str, datetime] = {
        'T': datetime.now(),
        'M': datetime.now() + timedelta(days=1),
    }
    target_time: datetime | None = options.get(query.data) # type: ignore
    selected_schedule: Schedule = context.user_data[SELECTED_SCHEDULE] # type: ignore

    timetable = await asu.get_timetable(selected_schedule.get_schedule_url())
    formatted_timetable = asu.format_schedule(
        timetable,
        selected_schedule.get_schedule_url(print_mode=False),
        selected_schedule.name,
        target_time)

    await query.edit_message_text(formatted_timetable, parse_mode=telegram.constants.ParseMode.MARKDOWN_V2)
    return END

async def find_schedule_of_group(group_name: str) -> Optional[Schedule]:
    return await asu.find_schedule_url(group_name)