import asyncio
from datetime import datetime, timedelta
import telegram
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, ConversationHandler

import asu.schedule as asu
from asu.group import Schedule

async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"Привет, {user.mention_html()}! Это бот для поиска расписания студентов и преподавателей АлтГУ.\n"
            "Используй контекстное меню или команды для взаимодействия с ботом.\n"
            "Если возникли ошибки или есть идеи, напиши нам.\n"
            "Контакты в описании бота")

async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    group_name: str = ""
    if context.args is not None and len(context.args) > 0:
        group_name = ''.join(context.args)

    if not group_name:
        await update.message.reply_text('Пожалуйста, введите название группы. Например: /schedule 305с11-4')
        return

    message = update.message
    message = await message.reply_text(text=f'Ищу расписание для группы: {group_name}...')

    group = asu.find_schedule_url(group_name)

    if group:
        # Запрос выбора расписания
        buttons = [
            [InlineKeyboardButton("Сегодня", callback_data=f"today:{group.faculty_id}:{group.group_id}")],
            [InlineKeyboardButton("Завтра", callback_data=f"tomorrow:{group.faculty_id}:{group.group_id}")],
            [InlineKeyboardButton("На всю неделю", callback_data=f"full_week:{group.faculty_id}:{group.group_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.edit_text(f"📚 Группа {group.name}\nВыберите, на какой день хотите получить расписание:", reply_markup=reply_markup)
    else:
        await message.edit_text("Ошибка получения группы.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()

    data = query.data.split(":")

    if len(data) != 3:
        # ban the user?
        return

    option = data[0].strip()
    faculty_id= data[1].strip()
    group_id = data[2].strip()

    group = Schedule("", int(faculty_id), int(group_id))

    await asyncio.sleep(1)

    response_text = asu.get_timetable(group.get_schedule_url())
    if isinstance(response_text, int):
        await query.edit_message_text("Произошла ошибка при получении расписания")
        logging.error(f'Ошибка {response_text} при получении расписания')
        return
    
    options = {
        "today": datetime.now(),
        "tomorrow": datetime.now() + timedelta(days=1)
    }
    target_time = options.get(option)

    formatted_timetable = asu.format_schedule(response_text, group.get_schedule_url(), "", target_time)

    await query.edit_message_text(formatted_timetable, parse_mode=telegram.constants.ParseMode.MARKDOWN_V2)
