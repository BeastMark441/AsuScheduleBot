from datetime import datetime, timedelta
from telegram import Update
import telegram
from telegram.ext import ContextTypes, ConversationHandler

import asu
from asu.group import Group
from asu.lecturer import Lecturer
from telegrambot.database import Database
from utils.daterange import DateRange


END = ConversationHandler.END
GET_GROUP_NAME, SHOW_SCHEDULE, SAVE_GROUP, GET_LECTURER_NAME, SHOW_LECTURER_SCHEDULE, SAVE_LECTURER, CHOOSE_SCHEDULE_TYPE = range(7)

SELECTED_SCHEDULE = 'schedule'

DATABASE = Database()

async def handle_show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик показа расписания"""

    if not (query := update.callback_query):
        return END
    
    _ = await query.answer()

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

    selected_schedule: Lecturer | Group = context.user_data[SELECTED_SCHEDULE]
    is_lecturer = isinstance(selected_schedule, Lecturer)  # Определяем тип расписания

    timetable = await asu.get_timetable(selected_schedule, target_date)
    formatted_timetable = asu.format_schedule(
        timetable,
        selected_schedule.get_schedule_url(),
        selected_schedule.name,
        target_date,
        is_lecturer  # Передаем флаг is_lecturer
    )

    await query.edit_message_text(formatted_timetable, parse_mode=telegram.constants.ParseMode.HTML)

    return END

async def exit_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data:
        context.user_data.pop(SELECTED_SCHEDULE)
    return END