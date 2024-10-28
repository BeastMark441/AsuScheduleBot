import asyncio
from datetime import datetime, timedelta
from typing import Optional, Union
import telegram
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
import asu
from asu import Schedule, Lecturer
from asu.schedule import ScheduleRequest  # Перемещаем ScheduleRequest в schedule.py

END = ConversationHandler.END
GET_GROUP_NAME, SHOW_SCHEDULE, SAVE_GROUP, GET_LECTURER_NAME, SHOW_LECTURER_SCHEDULE, SAVE_LECTURER, CHOOSE_SCHEDULE_TYPE = range(7)

SELECTED_SCHEDULE = 'schedule'

def get_next_weekday(d, weekday):
    # Функция для получения следующего заданного дня недели
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    return d + timedelta(days=days_ahead)

async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Обработчик команды /start
    user = update.effective_user
    await update.message.reply_html(
        f"Привет, {user.mention_html()}! Это бот для поиск расписания студентов и преподавателей АлтГУ.\n"
        "Используй контекстное меню или команды для взаимодействия с ботом.\n"
        "Если возникли ошибки или есть идеи, напиши нам.\n"
        "Контакты в описании бота"
    )

async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Обработчик команды /schedule
    user_id = update.effective_user.id
    db = context.bot_data['db']
    saved_group = db.get_group(user_id)
    if saved_group:
        await update.message.reply_text(f"Используется сохраненная группа: {saved_group}")
        return await handle_schedule(update, context, saved_group)
    
    if not context.args:
        await update.message.reply_text("Введите название группы:")
        return GET_GROUP_NAME
    
    group_name = ' '.join(context.args)
    return await handle_schedule(update, context, group_name)

async def get_group_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Обработчик ввода названия группы
    group_name = update.message.text
    if not group_name:
        await update.message.reply_text("Пожалуйста, введите корректное название группы.")
        return GET_GROUP_NAME
    return await handle_schedule(update, context, group_name)

async def handle_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, group_name: str) -> int:
    # Основной обработчик запроса расписания
    schedule = await find_schedule_of_group(group_name)
    if not schedule:
        await update.message.reply_text("Ошибка получения группы. Пожалуйста, проверьте название и попробуйте снова.")
        return END
    
    context.user_data[SELECTED_SCHEDULE] = schedule
    
    user_id = update.effective_user.id
    db = context.bot_data['db']
    if not db.get_group(user_id):
        return await ask_to_save_group(update, context, schedule.name)
    
    return await show_schedule_options(update, context)

async def ask_to_save_group(update: Update, context: ContextTypes.DEFAULT_TYPE, group_name: str) -> int:
    # Запрос на сохранение группы
    keyboard = [
        [InlineKeyboardButton("Да", callback_data="save_yes"),
         InlineKeyboardButton("Нет", callback_data="save_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Хотите ли вы сохранить группу {group_name} для быстрого доступа в будущем?",
        reply_markup=reply_markup
    )
    return SAVE_GROUP

async def save_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Обработчик ответа на запрос сохранения группы
    query = update.callback_query
    await query.answer()

    if query.data == "save_yes":
        schedule = context.user_data.get(SELECTED_SCHEDULE)
        if schedule:
            user_id = update.effective_user.id
            db = context.bot_data['db']
            db.save_group(user_id, schedule.name)
            await query.edit_message_text(f"Группа {schedule.name} сохранена.")
        else:
            await query.edit_message_text("Произошла ошибка при сохранении группы.")
    else:
        await query.edit_message_text("Группа не сохранена.")

    return await show_schedule_options(update, context)

async def show_schedule_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ок опций выбора периода расписания
    keyboard = [
        [InlineKeyboardButton("Сегодня", callback_data="T")],
        [InlineKeyboardButton("Завтра", callback_data="M")],
        [InlineKeyboardButton("На эту неделю", callback_data="W")],
        [InlineKeyboardButton("На следующую неделю", callback_data="NW")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]  # Добавляем кнопку отмены
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    schedule = context.user_data[SELECTED_SCHEDULE]
    if isinstance(update.effective_message, telegram.Message):
        await update.effective_message.reply_text(
            f"📚 Группа {schedule.name}\nВыберите, на какой день хотите получить расписание:",
            reply_markup=reply_markup
        )
    else:
        await update.callback_query.message.reply_text(
            f"📚 Группа {schedule.name}\nВыберите, на какой день хотите получить расписание:",
            reply_markup=reply_markup
        )
    
    return SHOW_SCHEDULE

async def cleansavegroup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Обработчик команды очистки сохраненной группы
    user_id = update.effective_user.id
    db = context.bot_data['db']
    saved_group = db.get_group(user_id)
    if saved_group:
        db.clear_group(user_id)
        await update.message.reply_text(f"Сохраненная группа {saved_group} удалена.")
    else:
        await update.message.reply_text("У вас нет сохраненной группы.")

async def handle_show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    today = datetime.now()
    
    if query.data == 'T':
        target_time = ScheduleRequest(today)
    elif query.data == 'M':
        target_time = ScheduleRequest(today + timedelta(days=1))
    elif query.data == 'W':
        week_start = today - timedelta(days=today.weekday())
        target_time = ScheduleRequest(week_start, is_week_request=True)
    else:  # NW
        next_week = today + timedelta(days=7-today.weekday())
        target_time = ScheduleRequest(next_week, is_week_request=True)

    selected_schedule = context.user_data[SELECTED_SCHEDULE]
    is_lecturer = isinstance(selected_schedule, Lecturer)  # Определяем тип расписания

    try:
        timetable_data = await asu.get_timetable(selected_schedule, target_time)
        formatted_timetable = asu.format_schedule(
            timetable_data,
            selected_schedule.get_schedule_url(print_mode=False),
            selected_schedule.name,
            target_time,
            is_lecturer=is_lecturer  # Передаем флаг is_lecturer
        )
        await query.edit_message_text(formatted_timetable, parse_mode=telegram.constants.ParseMode.MARKDOWN_V2)
    except Exception as e:
        logging.error(f"Ошибка при получении расписания: {e}")
        error_message = f"Произошла ошибка при получении расписания: {str(e)}\\. Пожалуйста, попробуйте позже\\."
        await query.edit_message_text(error_message)

    return END

async def find_schedule_of_group(group_name: str) -> Optional[Schedule]:
    # оск расписания для заданной группы
    return await asu.find_schedule_url(group_name)

async def lecturer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /lecturer"""
    user_id = update.effective_user.id
    db = context.bot_data['db']
    saved_lecturer = db.get_lecturer(user_id)
    
    if saved_lecturer:
        await update.message.reply_text(f"Используется сохраненный преподаватель: {saved_lecturer}")
        return await handle_lecturer_schedule(update, context, saved_lecturer)
    
    if not context.args:
        await update.message.reply_text("Введите фамилию преподавателя:")
        return GET_LECTURER_NAME
    
    lecturer_name = ' '.join(context.args)
    return await handle_lecturer_schedule(update, context, lecturer_name)

async def get_lecturer_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода фамилии преподавателя"""
    lecturer_name = update.message.text
    if not lecturer_name:
        await update.message.reply_text("Пожалуйста, введите корректную фамилию преподавателя.")
        return GET_LECTURER_NAME
    return await handle_lecturer_schedule(update, context, lecturer_name)

async def handle_lecturer_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, lecturer_name: str) -> int:
    """Основной обработчик запроса расписания преподавателя"""
    lecturer = await asu.find_lecturer_schedule(lecturer_name)
    if not lecturer:
        await update.message.reply_text(
            "Преподаватель не найден. Пожалуйста, проверьте правильность написания фамилии и попробуйте снова."
        )
        return END
    
    context.user_data[SELECTED_SCHEDULE] = lecturer
    
    user_id = update.effective_user.id
    db = context.bot_data['db']
    if not db.get_lecturer(user_id):
        return await ask_to_save_lecturer(update, context, lecturer.name)
    
    return await show_lecturer_schedule_options(update, context)

async def ask_to_save_lecturer(update: Update, context: ContextTypes.DEFAULT_TYPE, lecturer_name: str) -> int:
    keyboard = [
        [InlineKeyboardButton("Да", callback_data="save_lecturer_yes"),
         InlineKeyboardButton("Нет", callback_data="save_lecturer_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Хотите ли вы сохранить преподавателя {lecturer_name} для быстрого доступа в будущем?",
        reply_markup=reply_markup
    )
    return SAVE_LECTURER

async def save_lecturer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "save_lecturer_yes":
        lecturer = context.user_data.get(SELECTED_SCHEDULE)
        if lecturer:
            user_id = update.effective_user.id
            db = context.bot_data['db']
            db.save_lecturer(user_id, lecturer.name)
            await query.edit_message_text(f"Преподаватель {lecturer.name} сохранен.")
        else:
            await query.edit_message_text("Произошла ошибка при сохранении преподавателя.")
    else:
        await query.edit_message_text("Преподаватель не сохранен.")

    # Показываем опции расписания после сохранения/отказа
    return await show_lecturer_schedule_options(update, context)

async def cleansavelect_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db = context.bot_data['db']
    saved_lecturer = db.get_lecturer(user_id)
    if saved_lecturer:
        db.clear_lecturer(user_id)
        await update.message.reply_text(f"Сохраненный преподаватель {saved_lecturer} удален.")
    else:
        await update.message.reply_text("У вас нет сохраненного преподавателя.")

async def show_lecturer_schedule_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показ опций выбора периода расписания для преподавателя"""
    keyboard = [
        [InlineKeyboardButton("Сегодня", callback_data="T")],
        [InlineKeyboardButton("Завтра", callback_data="M")],
        [InlineKeyboardButton("На эту неделю", callback_data="W")],
        [InlineKeyboardButton("На следующую неделю", callback_data="NW")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]  # Добавляем кнопку отмены
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    lecturer = context.user_data[SELECTED_SCHEDULE]
    if isinstance(update.effective_message, telegram.Message):
        await update.effective_message.reply_text(
            f"👩‍🏫 Преподаватель: {lecturer.name}\nВыберите период расписания:",
            reply_markup=reply_markup
        )
    else:
        await update.callback_query.message.reply_text(
            f"👩‍🏫 Преподаватель: {lecturer.name}\nВыберите период расписания:",
            reply_markup=reply_markup
        )
    
    return SHOW_LECTURER_SCHEDULE

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает главное меню выбора типа расписания"""
    keyboard = [
        [InlineKeyboardButton("👩‍🏫 Расписание преподавателя", callback_data="choose_lecturer")],
        [InlineKeyboardButton(" Расписание группы", callback_data="choose_group")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if isinstance(update.callback_query, telegram.CallbackQuery):
        await update.callback_query.message.edit_text(
            "Выберите тип расписания:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "Выберите тип расписания:",
            reply_markup=reply_markup
        )
    return CHOOSE_SCHEDULE_TYPE

async def handle_schedule_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор типа расписания"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "choose_lecturer":
        await query.edit_message_text("Введите фамилию преподавателя:")
        return GET_LECTURER_NAME
    else:  # choose_group
        # Вместо вызова schedule_callback напрямую показываем сообщение
        await query.edit_message_text("Введите название группы:")
        return GET_GROUP_NAME

async def cancel_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик кнопки отмены"""
    query = update.callback_query
    await query.answer()
    return await show_main_menu(update, context)

# Обновляем ConversationHandler для расписания групп
schedule_handler = ConversationHandler(
    entry_points=[
        CommandHandler("schedule", schedule_callback),
        CommandHandler("shcedule", schedule_callback),
    ],
    states={
        GET_GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group_name)],
        GET_LECTURER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_lecturer_name)],
        SAVE_GROUP: [CallbackQueryHandler(save_group_callback, pattern='^save_yes|save_no$')],
        SHOW_SCHEDULE: [
            CallbackQueryHandler(handle_show_schedule, pattern='^T|M|W|NW$'),
            CallbackQueryHandler(cancel_schedule, pattern='^cancel$')
        ],
        SHOW_LECTURER_SCHEDULE: [  # Добавляем это состояние
            CallbackQueryHandler(handle_show_schedule, pattern='^T|M|W|NW$'),
            CallbackQueryHandler(cancel_schedule, pattern='^cancel$')
        ],
        CHOOSE_SCHEDULE_TYPE: [
            CallbackQueryHandler(handle_schedule_choice, pattern='^choose_(lecturer|group)$')
        ],
    },
    fallbacks=[CommandHandler("start", start_callback)],
    per_message=False,
    name="schedule_conversation"
)

# Обновляем ConversationHandler для расписания преподавателей
lecturer_handler = ConversationHandler(
    entry_points=[CommandHandler("lecturer", lecturer_callback)],
    states={
        GET_LECTURER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_lecturer_name)],
        GET_GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group_name)],
        SHOW_LECTURER_SCHEDULE: [
            CallbackQueryHandler(handle_show_schedule, pattern='^T|M|W|NW$'),
            CallbackQueryHandler(cancel_schedule, pattern='^cancel$')
        ],
        SHOW_SCHEDULE: [  # Добавляем это состояние
            CallbackQueryHandler(handle_show_schedule, pattern='^T|M|W|NW$'),
            CallbackQueryHandler(cancel_schedule, pattern='^cancel$')
        ],
        SAVE_LECTURER: [CallbackQueryHandler(save_lecturer_callback, pattern='^save_lecturer_yes|save_lecturer_no$')],
        CHOOSE_SCHEDULE_TYPE: [
            CallbackQueryHandler(handle_schedule_choice, pattern='^choose_(lecturer|group)$')
        ],
    },
    fallbacks=[CommandHandler("start", start_callback)],
    per_message=False,
    name="lecturer_conversation"
)
