import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ConversationHandler, MessageHandler, filters
from .common import *

# Состояния для ConversationHandler
GET_OTHER_GROUP = 1
WAITING_FOR_BUTTON = 2

async def card_callback(update: Update, context: ApplicationContext) -> int:
    """Обработчик команды /card - отправляет ссылку на техкарту группы"""

    if context.args:
        group_name = ''.join(context.args)
        group = await find_group_by_name(group_name)
        
        if group is None:
            await update.message.reply_text("Группа не найдена")
            return END
    else:
        group = await get_saved_group(update.effective_user)
        if group is None:
            await update.message.reply_text("У вас нет сохраненной группы. Используйте /schedule чтобы сохранить группу, или укажите группу после команды, например: /card 305с11-4")
            return END
    
    return await show_techcard(update, context, group)

async def find_group_by_name(group_name: str) -> models.Group | None:
    group_name = group_name[:50] # Limit to 50 symbols
    
    if not group_name:
        return None
    
    async for session in create_session():
        async with session.begin():
            group = await session.scalar(select(models.Group).where(models.Group.name.like("%{}%".format(group_name))))
            
            return group
        
    return None

async def show_techcard(update: Update, context: ApplicationContext, group: models.Group) -> int:
    """Показывает техкарту для указанной группы"""
    
    message = update.callback_query.message if update.callback_query else update.message
    
    if message is None or not isinstance(message, Message):
        return END
    
    # Ищем ссылку для группы
    techcard_url = group.technical_cards_link
    if techcard_url:
        # Создаем клавиатуру с кнопкой
        keyboard = [[InlineKeyboardButton("🔍 Найти для другой группы", callback_data="find_other")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.reply_text(
            f"📚 Техкарта для группы {group.name}:\n"
            + f"<a href='{html.escape(techcard_url)}'>Открыть на Яндекс.Диске</a>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        return WAITING_FOR_BUTTON
    else:
        await message.reply_text(
            f"Для группы {group.name} техкарта не найдена."
        )
        return END

async def find_other_callback(update: Update, context: ApplicationContext) -> int:
    """Обработчик нажатия кнопки 'Найти для другой группы'"""

    await update.callback_query.answer()
    
    await update.callback_query.message.chat.send_message("Введите номер группы (например: 305с11-4):")
    return GET_OTHER_GROUP

async def get_other_group(update: Update, context: ApplicationContext) -> int:
    """Обработчик ввода номера другой группы"""
    
    text = update.message.text or ""
    group = await find_group_by_name(text)
    
    if group is None:
        await update.message.reply_text(f"Группа {text} не найдена")
        return END

    return await show_techcard(update, context, group)

card_handler = ConversationHandler(
    entry_points=[CommandHandler("card", card_callback)],
    states={
        GET_OTHER_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_other_group)],
        WAITING_FOR_BUTTON: [CallbackQueryHandler(find_other_callback, pattern="^find_other$")]
    },
    fallbacks=[MessageHandler(filters.COMMAND, exit_conversation)],
    allow_reentry=True,
    per_message=False,
    per_user=True,
    per_chat=True,
    name="card_conversation"
) 