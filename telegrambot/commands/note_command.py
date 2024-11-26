from sqlalchemy import func
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus, ChatType
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters

from database.models import Note
from .common import *

CHOOSE_ACTION, ENTER_SUBJECT, ENTER_DATE, ENTER_NOTE, CONFIRM_DELETE = range(5)

async def notes_callback(update: Update, _context: ApplicationContext) -> int:
    """Обработчик команды /notes"""

    keyboard = [
        [
            InlineKeyboardButton("📝 Добавить заметку", callback_data="add_note"),
            InlineKeyboardButton("👀 Посмотреть заметки", callback_data="view_notes")
        ],
        [InlineKeyboardButton("❌ Удалить заметку", callback_data="delete_note")]
    ]
    
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSE_ACTION

async def action_handler(update: Update, context: ApplicationContext) -> int:
    """Обработчик выбора действия"""
    query = update.callback_query
    
    await query.answer()
    
    action = query.data
    if action == "add_note":
        # TODO: add decorator
        if update.effective_chat.type != ChatType.PRIVATE:
            # Check for permissions in groups
            member = await update.effective_chat.get_member(update.effective_user.id)
            if member.status not in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]:
                await update.message.reply_text(
                    "В групповом чате оставлять заметки могут только администраторы."
                )
                return END

        await query.edit_message_text("Введите название предмета:")
        return ENTER_SUBJECT
    elif action == "view_notes":
        return await show_notes(update, context)
    elif action == "delete_note":
        return await show_notes_for_deletion(update, context)
    
    return END

async def title_handler(update: Update, context: ApplicationContext) -> int:
    """Обработчик ввода предмета"""
    context.user_data.note = Note(title=update.message.text[:250])
    
    await update.message.reply_text(
        "Введите дату для заметки (в формате ДД.ММ.ГГГГ):"
    )
    return ENTER_DATE

async def date_handler(update: Update, context: ApplicationContext) -> int:
    """Обработчик ввода даты"""
    
    text = update.message.text or ""
    
    try:
        note_date = datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        await update.message.reply_text(
            "Неверный формат даты. Используйте формат ДД.ММ.ГГГГ"
        )
        return ENTER_DATE

    # Проверяем, что дата не более чем на 14 дней вперед
    today = datetime.now().date()
    max_date = today + timedelta(days=14)
    
    if note_date > max_date:
        await update.message.reply_text(
            "Нельзя создавать заметки более чем на 14 дней вперёд.\n"
            + f"Максимальная дата: {max_date.strftime('%d.%m.%Y')}"
        )
        return ENTER_DATE
        
    if note_date < today:
        await update.message.reply_text(
            "Нельзя создавать заметки на прошедшие даты.\n"
            + f"Минимальная дата: {today.strftime('%d.%m.%Y')}"
        )
        return ENTER_DATE
    
    context.user_data.note.timestamp = note_date
    
    await update.message.reply_text("Введите текст заметки:")
    return ENTER_NOTE

async def add_note(note: Note) -> bool:
    filter_by = Note.chat_id == note.chat_id if note.chat_id is not None else Note.user_id == note.user_id
    stmt = select(func.count(Note.id)).where(filter_by)

    async for session in create_session():
        async with session.begin():
            result = await session.execute(stmt)
            note_count = result.scalar() or 0
            if note_count > 6:
                return False
            
            
            session.add(note)
            await session.commit()
            
    return True

async def note_handler(update: Update, context: ApplicationContext) -> int:
    """Обработчик ввода текста заметки"""

    note = context.user_data.note
    assert note
    note.text = update.message.text[:500]
    note.user_id = update.effective_user.id
    note.chat_id = update.effective_chat.id if update.effective_chat.type != ChatType.PRIVATE else None
    
    success = await add_note(note)

    if success:
        await update.message.reply_text("✅ Заметка успешно добавлена!")
    else:
        await update.message.reply_text(
            "❌ Не удалось добавить заметку. Возможно, достигнут лимит заметок."
        )

    return END

async def get_notes(user_id: int, chat_id: int | None):
    filter_by = Note.chat_id == chat_id if chat_id is not None else Note.user_id == user_id
    stmt = select(Note).where(filter_by).order_by(Note.timestamp.desc())
    
    async for session in create_session():
        async with session.begin():
            return (await session.execute(stmt)).scalars().all()
        
async def show_notes(update: Update, context: ApplicationContext) -> int:
    """Показывает заметки пользователя"""
    
    await update.callback_query.answer()

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat.type != ChatType.PRIVATE else None
    
    notes = await get_notes(user_id, chat_id)
    
    if not notes:
        await update.callback_query.edit_message_text("У вас пока нет заметок.")
        return END
    
    text = "📝 Ваши заметки:\n\n"
    for note in notes:
        text += (
            f"📅 {note.timestamp}\n"
            f"📚 Предмет: {note.title}\n"
            f"✏️ Заметка: {note.text}\n"
        )
    
    await update.callback_query.edit_message_text(text)
    return END

async def show_notes_for_deletion(update: Update, context: ApplicationContext) -> int:
    """Показывает заметки для удаления"""
    
    await update.callback_query.answer()

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat.type != ChatType.PRIVATE else None
    
    notes = await get_notes(user_id, chat_id)
    
    if not notes:
        await update.callback_query.edit_message_text("У вас нет заметок для удаления.")
        return END
    
    keyboard: list[list[InlineKeyboardButton]] = []
    for note in notes:
        timestamp_str = note.timestamp.strftime("%d.%m.%Y")
        text = f"{timestamp_str} - {note.title}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"del_{note.id}")])
    
    await update.callback_query.edit_message_text(
        "Выберите заметку для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRM_DELETE

async def delete_note(note_id: int, user_id: int) -> bool:
    async for session in create_session():
        async with session.begin():
            row = await session.get(Note, note_id)
            
            if row and row.user_id == user_id:
                await session.delete(row)
                await session.commit()
                return True
            
    return False
            

async def delete_note_handler(update: Update, context: ApplicationContext) -> int:
    """Обработчик удаления заметки"""

    query = update.callback_query
    user_id = update.effective_user.id
    
    await query.answer()
    
    note_id = int(query.data.split('_')[1])
    user_id = update.effective_user.id
    
    if await delete_note(note_id, user_id):
        await query.edit_message_text("✅ Заметка успешно удалена!")
    else:
        await query.edit_message_text("❌ Не удалось удалить заметку.")
    
    return END

notes_handler = ConversationHandler(
    entry_points=[CommandHandler('notes', notes_callback)],
    states={
        CHOOSE_ACTION: [CallbackQueryHandler(action_handler, pattern="^(add_note|view_notes|delete_note)$")],
        ENTER_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, title_handler)],
        ENTER_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_handler)],
        ENTER_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, note_handler)],
        CONFIRM_DELETE: [CallbackQueryHandler(delete_note_handler, pattern="^del_[0-9]+$")]
    },
    fallbacks=[MessageHandler(filters.COMMAND, exit_conversation)],
    per_message=False,
    per_user=True,
    per_chat=True,
    name="notes_conversation"
)