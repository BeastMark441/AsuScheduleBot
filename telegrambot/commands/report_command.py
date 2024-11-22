from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CommandHandler, 
    ConversationHandler, 
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
import logging

from .common import DATABASE, END
from .admin_command import ADMIN_IDS

# Состояния
CATEGORY_SELECTION = 1
GROUP_INPUT = 2
LECTURER_INPUT = 3
TECHCARD_GROUP = 4
TECHCARD_LINK = 5
MESSAGE_INPUT = 6
CONFIRM_SEND = 7

# Callback data
CATEGORIES = {
    'group_schedule': 'Поиск расписания группы',
    'lecturer_schedule': 'Поиск расписания преподавателя',
    'techcard': 'Поиск тех.карты',
    'other': 'Другая',
    'start': 'Вернуться на старт'
}

async def report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /report"""
    if not ((message := update.message) and (user := message.from_user)):
        return END

    # Проверяем, не заблокирован ли пользователь
    if DATABASE.is_report_denied(user.id):
        await message.reply_text("Вам временно ограничен доступ к отправке отчетов об ошибках.")
        return END

    keyboard = [
        [InlineKeyboardButton(text, callback_data=data)]
        for data, text in CATEGORIES.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        "Если вы обнаружили ошибки, выберите одну из этих категорий:",
        reply_markup=reply_markup
    )
    return CATEGORY_SELECTION

async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора категории"""
    query = update.callback_query
    await query.answer()
    
    category = query.data
    context.user_data['report_category'] = category
    
    if category == 'start':
        await query.message.edit_text("Вы вернулись в главное меню.")
        return END
        
    if category == 'group_schedule':
        await query.message.edit_text("Введите номер вашей группы:")
        return GROUP_INPUT
        
    if category == 'lecturer_schedule':
        await query.message.edit_text("Введите Фамилию преподавателя:")
        return LECTURER_INPUT
        
    if category == 'techcard':
        await query.message.edit_text("Введите номер вашей группы:")
        return TECHCARD_GROUP
        
    if category == 'other':
        await query.message.edit_text(
            "Введите сообщение для администраторов и постарайтесь объяснить проблему:"
        )
        return MESSAGE_INPUT

async def group_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['group'] = update.message.text
    await update.message.reply_text(
        "Введите сообщение для администраторов и постарайтесь объяснить проблему:"
    )
    return MESSAGE_INPUT

async def lecturer_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['lecturer'] = update.message.text
    await update.message.reply_text(
        "Введите сообщение для администраторов и постарайтесь объяснить проблему:"
    )
    return MESSAGE_INPUT

async def techcard_group_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['group'] = update.message.text
    keyboard = [[InlineKeyboardButton("Ошибка не в этом", callback_data="not_link")]]
    await update.message.reply_text(
        "Если ошибка в том, что ссылка не верна или не актуальна. Введите ссылку на актуальную карту:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TECHCARD_LINK

async def techcard_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        context.user_data['techcard_link'] = None
        await update.callback_query.message.edit_text(
            "Введите сообщение для администраторов и постарайтесь объяснить проблему:"
        )
    else:
        context.user_data['techcard_link'] = update.message.text
        await update.message.reply_text(
            "Введите сообщение для администраторов и постарайтесь объяснить проблему:"
        )
    return MESSAGE_INPUT

async def message_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['message'] = update.message.text
    keyboard = [[InlineKeyboardButton("Отправить", callback_data="send")]]
    await update.message.reply_text(
        "Подтвердите отправку отчета:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRM_SEND

async def send_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    category = context.user_data.get('report_category')
    message = context.user_data.get('message')
    
    # Формируем сообщение для администраторов
    report_text = (
        f"📝 Новый отчет об ошибке\n"
        f"От пользователя: {user.id} ({user.username or 'без username'})\n"
        f"Категория: {CATEGORIES[category]}\n"
    )
    
    if category == 'group_schedule':
        report_text += f"Группа: {context.user_data.get('group')}\n"
    elif category == 'lecturer_schedule':
        report_text += f"Преподаватель: {context.user_data.get('lecturer')}\n"
    elif category == 'techcard':
        report_text += (
            f"Группа: {context.user_data.get('group')}\n"
            f"Ссылка: {context.user_data.get('techcard_link') or 'не указана'}\n"
        )
    
    report_text += f"\nСообщение:\n{message}"
    
    # Кнопки для администраторов
    keyboard = [
        [
            InlineKeyboardButton("✅ Принято", callback_data=f"report_accept_{user.id}"),
            InlineKeyboardButton("❌ Отклонено", callback_data=f"report_reject_{user.id}")
        ],
        [InlineKeyboardButton("🚫 Заблокировать", callback_data=f"report_block_{user.id}")]
    ]
    
    # Отправляем в чат разработчиков
    await context.bot.send_message(
        chat_id=context.application.bot_data['DEVELOPER_CHAT_ID'],
        text=report_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    await query.message.edit_text(
        "Ваш отчет отправлен! В скором времени его рассмотрят."
    )
    return END

async def admin_report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик действий администратора по отчету"""
    query = update.callback_query
    if not query:
        return
        
    await query.answer()
    
    action, user_id = query.data.rsplit('_', 1)
    user_id = int(user_id)
    
    try:
        if action == 'report_block':
            DATABASE.set_report_denied(user_id, True)
            await query.message.reply_text(f"Пользователь {user_id} заблокирован для отправки отчетов")
            # Уведомляем пользователя
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Вам ограничен доступ к отправке отчето�� об ошибках."
            )
        
        elif action == 'report_accept':
            # Уведомляем пользователя о принятии отчета
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ Ваш отчет об ошибке принят и будет обработан."
            )
            
        elif action == 'report_reject':
            # Уведомляем пользователя об отклонении отчета
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Ваш отчет об ошибке отклонен."
            )
        
        # Обновляем клавиатуру сообщения
        keyboard = [
            [
                InlineKeyboardButton("✅ Принято", callback_data=f"report_accepted_{user_id}"),
                InlineKeyboardButton("❌ Отклонено", callback_data=f"report_rejected_{user_id}")
            ]
        ]
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        
    except TelegramError as e:
        logging.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
        await query.message.reply_text(f"Не удалось отправить уведомление пользователю {user_id}")

report_handler = ConversationHandler(
    entry_points=[CommandHandler('report', report_callback)],
    states={
        CATEGORY_SELECTION: [
            CallbackQueryHandler(category_handler)
        ],
        GROUP_INPUT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, group_input_handler)
        ],
        LECTURER_INPUT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, lecturer_input_handler)
        ],
        TECHCARD_GROUP: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, techcard_group_handler)
        ],
        TECHCARD_LINK: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, techcard_link_handler),
            CallbackQueryHandler(techcard_link_handler, pattern="^not_link$")
        ],
        MESSAGE_INPUT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, message_input_handler)
        ],
        CONFIRM_SEND: [
            CallbackQueryHandler(send_report, pattern="^send$")
        ]
    },
    fallbacks=[],
    name="report_conversation"
)

# Добавляем обработчик действий администратора
admin_report_callback = CallbackQueryHandler(
    admin_report_handler,
    pattern="^report_(accept|reject|block)_[0-9]+$"
)

async def unblock_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /unblock"""
    if not ((message := update.message) and (user := update.effective_user)):
        return
        
    if user.id not in ADMIN_IDS:
        await message.reply_text("У вас нет прав для использования этой команды.")
        return
    
    if not context.args:
        await message.reply_text("Укажите ID пользователя для разблокировки.\nПример: /unblock 123456789")
        return
        
    try:
        user_id = int(context.args[0])
        DATABASE.set_report_denied(user_id, False)
        await message.reply_text(f"Пользователь {user_id} разблокирован для отправки отчетов.")
    except ValueError:
        await message.reply_text("Некорректный ID пользователя.")
    except Exception as e:
        logging.error(f"Ошибка при разблокировке пользователя: {e}")
        await message.reply_text("Произошла ошибка при разблокировке пользователя.")

unblock_handler = CommandHandler("unblock", unblock_callback) 