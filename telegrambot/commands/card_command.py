import json
import logging
from pathlib import Path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ConversationHandler, MessageHandler, filters
from .common import *

# Состояния для ConversationHandler
GET_OTHER_GROUP = 1
WAITING_FOR_BUTTON = 2

async def card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /card - отправляет ссылку на техкарту группы"""
    if not ((message := update.message) and (user := message.from_user)):
        return END
    
    # Определяем группу: из аргументов команды или сохраненную
    group_name = None
    
    if context.args:  # Если переданы аргументы команды
        # Собираем все аргументы в одну строку
        input_group = ''.join(context.args)
        # Добавляем префикс К. если его нет
        group_name = f"К.{input_group}" if not input_group.startswith('К.') else input_group
        return await show_techcard(update, context, group_name)
    else:  # Если аргументов нет, используем сохраненную группу
        group_name = DATABASE.get_group(user.id)
        if not group_name:
            await message.reply_text(
                "У вас нет сохраненной группы. Используйте /schedule чтобы сохранить группу, "
                "или укажите группу после команды, например: /card 305с11-4"
            )
            return END
        return await show_techcard(update, context, group_name)

async def show_techcard(update: Update, context: ContextTypes.DEFAULT_TYPE, group_name: str) -> int:
    """Показывает техкарту для указанной группы"""
    message = update.callback_query.message if update.callback_query else update.message
    if not message:
        return END
    
    # Загружаем данные техкарт
    techcards_path = Path(__file__).parent.parent / "data" / "techcards.json"
    try:
        with open(techcards_path, 'r', encoding='utf-8') as f:
            techcards = json.load(f)
    except Exception as e:
        logging.error(f"Ошибка при загрузке техкарт: {e}")
        await message.reply_text("Произошла ошибка при поиске техкарты.")
        return END
    
    # Ищем ссылку для группы
    techcard_url = techcards.get(group_name)
    if techcard_url:
        # Создаем клавиатуру с кнопкой
        keyboard = [[InlineKeyboardButton("🔍 Найти для другой группы", callback_data="find_other")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.reply_text(
            f"📚 Техкарта для группы {group_name}:\n"
            f"<a href='{techcard_url}'>Открыть на Яндекс.Диске</a>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        return WAITING_FOR_BUTTON
    else:
        await message.reply_text(
            f"Для группы {group_name} техкарта не найдена."
        )
        return END

async def find_other_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик нажатия кнопки 'Найти для другой группы'"""
    if not (query := update.callback_query):
        return END
    
    await query.answer()
    await query.message.reply_text(
        "Введите номер группы (например: 305с11-4):"
    )
    return GET_OTHER_GROUP

async def get_other_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода номера другой группы"""
    if not ((message := update.message) and (group_name := message.text)):
        return END
    
    # Добавляем префикс К. если его нет
    group_name = f"К.{group_name}" if not group_name.startswith('К.') else group_name
    return await show_techcard(update, context, group_name)

# Создаем ConversationHandler для команды card
card_handler = ConversationHandler(
    entry_points=[
        CommandHandler("card", card_callback),
    ],
    states={
        GET_OTHER_GROUP: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_other_group)
        ],
        WAITING_FOR_BUTTON: [
            CallbackQueryHandler(find_other_callback, pattern="^find_other$")
        ]
    },
    fallbacks=[MessageHandler(filters.COMMAND, lambda u, c: END)],
    allow_reentry=True,
    name="card_conversation"
) 