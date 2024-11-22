from datetime import datetime, timedelta
from telegram import Update
import telegram
from telegram.ext import ContextTypes, ConversationHandler
import logging

import asu
from asu.group import Group
from asu.lecturer import Lecturer
from telegrambot.database import Database
from utils.daterange import DateRange
from config import BOT_ADMIN_IDS

END = ConversationHandler.END
DATABASE = Database()

# Group states
GET_GROUP_NAME, SAVE_GROUP, SHOW_SCHEDULE = range(3)
# Lecturer states
GET_LECTURER_NAME, SAVE_LECTURER, SHOW_LECTURER_SCHEDULE = range(3, 6)

SELECTED_SCHEDULE = 'schedule'

async def handle_show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик показа расписания"""
    if not update.callback_query:
        return END

    query = update.callback_query
    await query.answer()

    if not context.user_data:
        await query.message.edit_text("Произошла ошибка. Попробуйте начать сначала.")
        return END

    today = datetime.now()
    
    if query.data == 'T': # Today
        target_date = DateRange(today)
    elif query.data == 'M': # Tomorrow
        target_date = DateRange(today + timedelta(days=1))
    elif query.data == 'W': # This Week
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        target_date = DateRange(week_start, week_end)
    else:  # Next Week
        next_week_start = today + timedelta(days=7-today.weekday())
        next_week_end = next_week_start + timedelta(days=6)
        target_date = DateRange(next_week_start, next_week_end)

    selected_schedule = context.user_data.get(SELECTED_SCHEDULE)
    if not selected_schedule:
        await query.message.edit_text("Произошла ошибка. Попробуйте начать сначала.")
        return END

    is_lecturer = isinstance(selected_schedule, Lecturer)

    try:
        timetable = await asu.get_timetable(selected_schedule, target_date)
        formatted_timetable = asu.format_schedule(
            timetable,
            selected_schedule.get_schedule_url(),
            selected_schedule.name,
            target_date,
            is_lecturer
        )

        await query.edit_message_text(
            formatted_timetable, 
            parse_mode=telegram.constants.ParseMode.HTML
        )
    except Exception as e:
        logging.error(f"Ошибка при получении расписания: {e}")
        await query.message.edit_text("Произошла ошибка при получении расписания.")
        return END

    return END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Общий обработчик отмены диалога"""
    if update.message:
        await update.message.reply_text("Действие отменено.")
    if context.user_data:
        context.user_data.clear()
    return END

async def check_group_permissions(update: Update, user_id: int) -> bool:
    """Проверяет права пользователя в групповом чате"""
    if update.effective_chat and update.effective_chat.type != 'private':
        member = await update.effective_chat.get_member(user_id)
        return member.status in ['creator', 'administrator'] or user_id in BOT_ADMIN_IDS
    return True  # В личных чатах всегда разрешено