from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters
from .common import *

async def lecturer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /lecturer"""
    
    if not ((message := update.message) and (user := message.from_user)):
        return END
    
    # В групповых чатах сохранение преподавателя доступно только администраторам
    is_group_chat = message.chat.type != 'private'
    can_save = await check_group_permissions(update, user.id)
    
    lecturer_name: str
    
    if context.args:
        lecturer_name = ''.join(context.args)
    elif (lecturer_name := DATABASE.get_lecturer(user.id) if not is_group_chat else None):
        await update.message.reply_text(f"Используется сохраненный преподаватель: {lecturer_name}")
    else:
        await update.message.reply_text(
            "Введите фамилию преподавателя:" if can_save else 
            "В групповом чате необходимо указывать преподавателя после команды, например: /lecturer Иванов"
        )
        return GET_LECTURER_NAME if can_save else END
    
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
    if not DATABASE.get_lecturer(user_id):
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
            DATABASE.save_lecturer(user_id, lecturer.name)
        else:
            await query.edit_message_text("Произошла ошибка при сохранении преподавателя.")

    # Показываем опции расписания после сохранения/отказа
    return await show_lecturer_schedule_options(update, context)

async def show_lecturer_schedule_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показ опций выбора периода расписания для преподавателя"""
    keyboard = [
        [InlineKeyboardButton("Сегодня", callback_data="T")],
        [InlineKeyboardButton("Завтра", callback_data="M")],
        [InlineKeyboardButton("На эту неделю", callback_data="W")],
        [InlineKeyboardButton("На следующую неделю", callback_data="NW")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    lecturer: Lecturer = context.user_data[SELECTED_SCHEDULE]
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
    fallbacks=[MessageHandler(filters.COMMAND, cancel_conversation)],
    allow_reentry=True,
    per_message=False,
    per_user=True,
    per_chat=True,
    name="lecturer_conversation"
)