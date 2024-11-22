from datetime import datetime, date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, 
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.error import TelegramError
from .common import DATABASE, END
from config import BOT_ADMIN_IDS, check_admin_rights

# Состояния
CHOOSE_ACTION = 1
ENTER_SUBJECT = 2
ENTER_DATE = 3
ENTER_NOTE = 4
CONFIRM_DELETE = 5

async def notes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /notes"""
    if not ((message := update.message) and (user := message.from_user)):
        return END

    # Проверяем права в групповом чате
    if message.chat.type != 'private':
        member = await message.chat.get_member(user.id)
        if member.status not in ['creator', 'administrator'] and user.id not in BOT_ADMIN_IDS:
            await message.reply_text(
                "В групповом чате оставлять заметки могут только администраторы."
            )
            return END

    keyboard = [
        [
            InlineKeyboardButton("📝 Добавить заметку", callback_data="add_note"),
            InlineKeyboardButton("👀 Посмотреть заметки", callback_data="view_notes")
        ],
        [InlineKeyboardButton("❌ Удалить заметку", callback_data="delete_note")]
    ]
    
    await message.reply_text(
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSE_ACTION

async def action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора действия"""
    if not (query := update.callback_query):
        return await cancel_notes(update, context)
        
    await query.answer()
    
    action = query.data
    if action == "add_note":
        await query.message.edit_text("Введите название предмета:")
        return ENTER_SUBJECT
    elif action == "view_notes":
        return await show_notes(update, context)
    elif action == "delete_note":
        return await show_notes_for_deletion(update, context)
    
    return await cancel_notes(update, context)

async def subject_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода предмета"""
    if not update.message:
        return await cancel_notes(update, context)
        
    if not context.user_data:
        context.user_data.clear()  # Очищаем существующий словарь
        
    context.user_data['subject'] = update.message.text
    
    await update.message.reply_text(
        "Введите дату для заметки (в формате ДД.ММ.ГГГГ):"
    )
    return ENTER_DATE

async def date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода даты"""
    if not update.message or not update.message.text:
        return await cancel_notes(update, context)
        
    try:
        note_date = datetime.strptime(update.message.text, "%d.%m.%Y").date()
        
        # Проверяем, что дата не более чем на 14 дней вперед
        today = datetime.now().date()
        max_date = today + timedelta(days=14)
        
        if note_date > max_date:
            await update.message.reply_text(
                "Нельзя создавать заметки более чем на 14 дней вперёд.\n"
                f"Максимальная дата: {max_date.strftime('%d.%m.%Y')}"
            )
            return ENTER_DATE
            
        if note_date < today:
            await update.message.reply_text(
                "Нельзя создавать заметки на прошедшие даты.\n"
                f"Минимальная дата: {today.strftime('%d.%m.%Y')}"
            )
            return ENTER_DATE
        
        context.user_data['note_date'] = note_date
        
        await update.message.reply_text("Введите текст заметки:")
        return ENTER_NOTE
        
    except ValueError:
        await update.message.reply_text(
            "Неверный формат даты. Используйте формат ДД.ММ.ГГГГ"
        )
        return ENTER_DATE

async def note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода текста заметки"""
    if not (update.message and update.effective_user and update.effective_chat):
        return await cancel_notes(update, context)
        
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not all(key in context.user_data for key in ['subject', 'note_date']):
        await update.message.reply_text("Произошла ошибка. Попробуйте начать сначала.")
        return await cancel_notes(update, context)
    
    success = DATABASE.add_note(
        user_id=user_id,
        chat_id=chat_id,
        subject=context.user_data['subject'],
        note_text=update.message.text,
        note_date=context.user_data['note_date']
    )
    
    if success:
        await update.message.reply_text("✅ Заметка успешно добавлена!")
    else:
        await update.message.reply_text(
            "❌ Не удалось добавить заметку. Возможно, достигнут лимит заметок."
        )
    
    # Очищаем данные после успешного добавления
    context.user_data.clear()
    return await cancel_notes(update, context)

async def show_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает заметки пользователя"""
    if not (query := update.callback_query):
        return await cancel_notes(update, context)
        
    if not update.effective_user or not update.effective_chat:
        await query.message.edit_text("Произошла ошибка. Попробуйте позже.")
        return await cancel_notes(update, context)
        
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    notes = DATABASE.get_notes(user_id, chat_id)
    
    if not notes:
        await query.message.edit_text("У вас пока нет заметок.")
        return await cancel_notes(update, context)
    
    text = "📝 Ваши заметки:\n\n"
    for note in notes:
        note_id, subject, note_text, note_date, author_id = note
        # Преобразуем строку в объект datetime, если это строка
        if isinstance(note_date, str):
            try:
                note_date = datetime.strptime(note_date, '%Y-%m-%d').date()
            except ValueError:
                # Если не удалось преобразовать, используем строку как есть
                formatted_date = note_date
            else:
                formatted_date = note_date.strftime('%d.%m.%Y')
        else:
            formatted_date = note_date.strftime('%d.%m.%Y')
            
        text += (
            f"📅 {formatted_date}\n"
            f"📚 Предмет: {subject}\n"
            f"✏️ Заметка: {note_text}\n"
            f"🆔 ID: {note_id}\n\n"
        )
    
    await query.message.edit_text(text)
    return await cancel_notes(update, context)

async def show_notes_for_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает заметки для удаления"""
    if not (query := update.callback_query):
        return await cancel_notes(update, context)
        
    if not update.effective_user or not update.effective_chat:
        await query.message.edit_text("Произошла ошибка. Попробуйте позже.")
        return await cancel_notes(update, context)
        
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    notes = DATABASE.get_notes(user_id, chat_id)
    
    if not notes:
        await query.message.edit_text("У вас нет заметок для удаления.")
        return await cancel_notes(update, context)
    
    keyboard = []
    for note in notes:
        note_id, subject, _, note_date, _ = note
        # Преобразуем строку в объект datetime, если это строка
        if isinstance(note_date, str):
            try:
                note_date = datetime.strptime(note_date, '%Y-%m-%d').date()
                formatted_date = note_date.strftime('%d.%m.%Y')
            except ValueError:
                formatted_date = note_date
        else:
            formatted_date = note_date.strftime('%d.%m.%Y')
            
        text = f"{formatted_date} - {subject}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"del_{note_id}")])
    
    await query.message.edit_text(
        "Выберите заметку для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRM_DELETE

async def delete_note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик удаления заметки"""
    if not (query := update.callback_query):
        return END
        
    user_id = update.effective_user.id
    
    # Проверяем права на удаление заметок
    if not await check_admin_rights(update, user_id, 'can_delete_notes'):
        await query.answer("У вас нет прав для удаления этой заметки")
        return END
    
    await query.answer()
    
    note_id = int(query.data.split('_')[1])
    user_id = update.effective_user.id
    
    if DATABASE.delete_note(note_id, user_id):
        await query.message.edit_text("✅ Заметка успешно удалена!")
    else:
        await query.message.edit_text("❌ Не удалось удалить заметку.")
    
    return await cancel_notes(update, context)

async def cancel_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена работы с заметками"""
    if update.message:
        await update.message.reply_text("Работа с заметками отменена.")
    if context.user_data:
        context.user_data.clear()
    return END  # Просто возвращаем END вместо рекурсивного вызова

# Создаем ConversationHandler для команды notes
notes_handler = ConversationHandler(
    entry_points=[CommandHandler('notes', notes_callback)],
    states={
        CHOOSE_ACTION: [
            CallbackQueryHandler(action_handler, pattern="^(add_note|view_notes|delete_note)$")
        ],
        ENTER_SUBJECT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subject_handler)
        ],
        ENTER_DATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, date_handler)
        ],
        ENTER_NOTE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, note_handler)
        ],
        CONFIRM_DELETE: [
            CallbackQueryHandler(delete_note_handler, pattern="^del_[0-9]+$")
        ]
    },
    fallbacks=[MessageHandler(filters.COMMAND, cancel_notes)],
    per_message=False,
    per_user=True,
    per_chat=True,
    name="notes_conversation"
)

# Функция для периодической очистки старых заметок
async def cleanup_notes(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Периодически очищает старые заметки"""
    DATABASE.cleanup_old_notes() 