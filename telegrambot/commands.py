import asyncio
from datetime import datetime, timedelta
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
from asu import Group, Lecturer
from telegrambot.database import Database
from utils.daterange import DateRange

END = ConversationHandler.END
GET_GROUP_NAME, SHOW_SCHEDULE, SAVE_GROUP, GET_LECTURER_NAME, SHOW_LECTURER_SCHEDULE, SAVE_LECTURER, CHOOSE_SCHEDULE_TYPE = range(7)

SELECTED_SCHEDULE = 'schedule'

database = Database()

async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    if ((message := update.message) and (user := message.from_user)):
        _ = await message.reply_html(
        f"Привет, {user.mention_html()}! Это бот для поиск расписания студентов и преподавателей АлтГУ.\n"
        + "Используй контекстное меню или команды для взаимодействия с ботом.\n"
        + "Если возникли ошибки или есть идеи, напиши нам.\n"
        + "Контакты в описании бота")

async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /schedule"""
    
    if not ((message := update.message) and (user := message.from_user)):
        return END
    
    # If user enters group name after the command, then search for it
    # If no input, then use saved, otherwise ask user to enter group
    
    group_name: str
    
    if context.args:
        group_name = ''.join(context.args)
    elif (group_name := database.get_group(user.id)): # pyright: ignore
        _ = await update.message.reply_text(f"Используется сохраненная группа: {group_name}")
    else:
        _ = await update.message.reply_text("Введите название группы:")
        return GET_GROUP_NAME
    
    return await handle_schedule(update, context, group_name)

async def get_group_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода названия группы"""
    
    if not ((message := update.message) and (group_name := message.text)):
        return END
    
    if not group_name:
        _ = await message.reply_text("Пожалуйста, введите корректное название группы")
        return GET_GROUP_NAME
    
    return await handle_schedule(update, context, group_name)

async def handle_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, group_name: str) -> int:
    """Основной обработчик запроса расписания"""
    
    schedule = await find_schedule_of_group(group_name)
    if not schedule:
        await update.message.reply_text("Ошибка получения группы. Пожалуйста, проверьте название и попробуйте снова")
        return END
    
    context.user_data[SELECTED_SCHEDULE] = schedule
    
    if not database.get_group(update.message.from_user.id):
        return await ask_to_save_group(update, context, schedule.name)
    
    return await show_schedule_options(update, context)

async def ask_to_save_group(update: Update, context: ContextTypes.DEFAULT_TYPE, group_name: str) -> int:
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

async def save_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ответа на запрос сохранения группы"""
    if not (query := update.callback_query):
        return END
    
    _ = await query.answer()

    if query.data == "save_yes":
        schedule = context.user_data.get(SELECTED_SCHEDULE)
        if isinstance(schedule, Group):
            user_id = update.effective_user.id
            database.save_group(user_id, schedule.name)
            _ = await query.edit_message_text(f"Группа {schedule.name} сохранена.")
        else:
            _ = await query.edit_message_text("Произошла ошибка при сохранении группы.")

    return await show_schedule_options(update, context)

async def show_schedule_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать опции выбора периода расписания"""
    keyboard = [
        [InlineKeyboardButton("Сегодня", callback_data="T")],
        [InlineKeyboardButton("Завтра", callback_data="M")],
        [InlineKeyboardButton("На эту неделю", callback_data="W")],
        [InlineKeyboardButton("На следующую неделю", callback_data="NW")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]  # Добавляем кнопку отмены
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    schedule = context.user_data[SELECTED_SCHEDULE]
    await update.effective_message.reply_text(
            f"📚 Группа {schedule.name}\nВыберите, на какой день хотите получить расписание:",
            reply_markup=reply_markup)
    
    return SHOW_SCHEDULE

async def cleansavegroup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды очистки сохраненной группы"""
    user_id = update.message.from_user.id
    saved_group = database.get_group(user_id)
    if saved_group:
        database.clear_group(user_id)
        await update.message.reply_text(f"Сохраненная группа {saved_group} удалена.")
    else:
        await update.message.reply_text("У вас нет сохраненной группы.")

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

    selected_schedule: Lecturer | Group = context.user_data[SELECTED_SCHEDULE] # pyright: ignore
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

async def lecturer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /lecturer"""
    
    if not ((message := update.message) and (user := message.from_user)):
        return END
    
    lecturer_name: str
    
    if context.args:
        lecturer_name = ''.join(context.args)
    elif (lecturer_name := database.get_lecturer(user.id)):
        await update.message.reply_text(f"Используется сохраненный преподаватель: {lecturer_name}")
    else:
        await update.message.reply_text("Введите фамилию преподавателя:")
        return GET_LECTURER_NAME
    
    return await handle_lecturer_schedule(update, context, lecturer_name)

async def get_lecturer_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода фамилии преподавателя"""
    
    if not ((message := update.message) and (lecturer_name := message.text)):
        return END
    
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
    if not database.get_lecturer(user_id):
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
    if not (query := update.callback_query):
        return END
    
    query = update.callback_query
    _ = await query.answer()

    if query.data == "save_lecturer_yes":
        lecturer = context.user_data.get(SELECTED_SCHEDULE)
        if lecturer:
            user_id = update.effective_user.id
            database.save_lecturer(user_id, lecturer.name)
        else:
            await query.edit_message_text("Произошла ошибка при сохранении преподавателя.")

    # Показываем опции расписания после сохранения/отказа
    return await show_lecturer_schedule_options(update, context)

async def cleansavelect_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    saved_lecturer = database.get_lecturer(user_id)
    if saved_lecturer:
        database.clear_lecturer(user_id)
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
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    lecturer = context.user_data[SELECTED_SCHEDULE]
    await update.effective_message.reply_text(
            f"👩‍🏫 Преподаватель: {lecturer.name}\nВыберите период расписания:",
            reply_markup=reply_markup)
    
    return SHOW_LECTURER_SCHEDULE

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает главное меню выбора типа расписания"""
    keyboard = [
        [InlineKeyboardButton("👩‍🏫 Расписание преподавателя", callback_data="choose_lecturer")],
        [InlineKeyboardButton(" Расписание группы", callback_data="choose_group")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.effective_message.edit_text(
            "Выберите тип расписания:",
            reply_markup=reply_markup)
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

async def exit_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data:
        context.user_data.pop(SELECTED_SCHEDULE)
    return END

async def find_schedule_of_group(group_name: str) -> Group | None:
    # Поиск расписания для заданной группы
    return await asu.find_schedule_url(group_name)

# Обновляем ConversationHandler для расписания групп
schedule_handler = ConversationHandler(
    entry_points=[
        CommandHandler("schedule", schedule_callback),
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
    fallbacks=[MessageHandler(filters.COMMAND, exit_conversation)],
    allow_reentry=True,
    # https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-Asked-Questions#what-do-the-per_-settings-in-conversationhandler-do
    per_message=False,
    per_user=False,
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
    fallbacks=[MessageHandler(filters.COMMAND, exit_conversation)],
    allow_reentry=True,
    # https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-Asked-Questions#what-do-the-per_-settings-in-conversationhandler-do
    per_message=False,
    per_user=False,
    name="lecturer_conversation"
)
