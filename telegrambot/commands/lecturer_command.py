from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters

from database.models import Lecturer, SearchType
from .common import *

async def lecturer_callback(update: Update, context: ApplicationContext) -> int:
    """Обработчик команды /lecturer"""
    
    lecturer_name = ''.join(context.args) if context.args else ""
    if lecturer_name:
        return await handle_lecturer_by_name(update, context, lecturer_name)
    
    lecturer = await get_saved_lecturer(update.effective_user)
    if lecturer:
        await add_statistics(update.effective_user, SearchType.lecturer, lecturer.name)
        
        context.user_data.selected_schedule = lecturer
        return await show_lecturer_options(update, context)
    
    await update.message.reply_text("Введите фамилию преподавателя:")
    return GET_LECTURER_NAME

async def get_lecturer_name(update: Update, context: ApplicationContext) -> int:
    """Обработчик ввода фамилии преподавателя"""
    
    if not (lecturer_name := update.message.text):
        return END
    
    if not lecturer_name:
        await update.message.reply_text("Пожалуйста, введите корректную фамилию преподавателя")
        return GET_GROUP_NAME
    
    return await handle_lecturer_by_name(update, context, lecturer_name)

async def handle_lecturer_by_name(update: Update, context: ApplicationContext, lecturer_name: str) -> int:
    """Основной обработчик запроса расписания преподавателя"""
    
    # Limit to 50 symbols
    lecturer_name = lecturer_name.strip()[:50]
    
    await add_statistics(update.effective_user, SearchType.lecturer, lecturer_name)
    
    lecturer = await asu.client.search_lecturer(lecturer_name)
    if not lecturer:
        await update.message.reply_text(
            "Преподаватель не найден. Пожалуйста, проверьте правильность написания фамилии и попробуйте снова."
        )
        return END
    
    context.user_data.selected_schedule = lecturer
    
    if not (saved_lecturer := await get_saved_lecturer(update.effective_user)) \
        or saved_lecturer.lecturer_id != lecturer.lecturer_id:
            # Checking by lecturer id might be bad idea?
            return await ask_to_save_lecturer(update, context, lecturer.name)
    
    return await show_lecturer_options(update, context)

async def ask_to_save_lecturer(update: Update, _context: ApplicationContext, lecturer_name: str) -> int:
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

async def save_lecturer_callback(update: Update, context: ApplicationContext) -> int:
    if not (query := update.callback_query):
        return END
    
    query = update.callback_query
    await query.answer()

    if query.data == "save_lecturer_yes":
        lecturer = context.user_data.selected_schedule
        if isinstance(lecturer, Lecturer):
            await set_saved_lecturer(update.effective_user, lecturer)
            await query.edit_message_text(f"Преподаватель {lecturer.name} сохранен.")
        else:
            await query.edit_message_text("Произошла ошибка при сохранении преподавателя.")

    # Показываем опции расписания после сохранения/отказа
    return await show_lecturer_options(update, context)

async def show_lecturer_options(update: Update, context: ApplicationContext) -> int:
    """Показ опций выбора периода расписания для преподавателя"""
    keyboard = [
        [InlineKeyboardButton("Сегодня", callback_data="T")],
        [InlineKeyboardButton("Завтра", callback_data="M")],
        [InlineKeyboardButton("На эту неделю", callback_data="W")],
        [InlineKeyboardButton("На следующую неделю", callback_data="NW")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    lecturer = context.user_data.selected_schedule
    await update.effective_message.reply_text(
            f"👩‍🏫 Преподаватель: {lecturer.name}\nВыберите период расписания:",
            reply_markup=reply_markup)
    
    return SHOW_LECTURER_SCHEDULE

lecturer_handler = ConversationHandler(
    entry_points=[CommandHandler("lecturer", lecturer_callback)],
    states={
        GET_LECTURER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_lecturer_name)],
        SHOW_LECTURER_SCHEDULE: [
            CallbackQueryHandler(handle_show_schedule, pattern='^T|M|W|NW$')
        ],
        SAVE_LECTURER: [CallbackQueryHandler(save_lecturer_callback, pattern='^save_lecturer_yes|save_lecturer_no$')],
    },
    fallbacks=[MessageHandler(filters.COMMAND, exit_conversation)],
    allow_reentry=True,
    per_message=False,
    per_user=True,
    per_chat=True,
    name="lecturer_conversation"
)