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

from .common import DATABASE, END, check_group_permissions
from config import BOT_ADMIN_IDS, check_admin_rights

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

# Кэшируем клавиатуры, чтобы не создавать их каждый раз
REPORT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton(text, callback_data=data)]
    for data, text in CATEGORIES.items()
])

CONFIRM_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("Отправить", callback_data="send")
]])

NOT_LINK_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("Ошибка не в этом", callback_data="not_link")
]])

async def report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /report"""
    if not ((message := update.message) and (user := message.from_user)):
        return END

    # Проверяем, не заблокирован ли пользователь
    if DATABASE.is_report_denied(user.id):
        await message.reply_text(
            "❌ У вас ограничен доступ к отправке отчетов об ошибках.\n"
            "Если вы считаете, что это ошибка, обратитесь к администраторам."
        )
        return END

    # В групповых чатах только администраторы могут отправлять отчеты
    if not await check_group_permissions(update, user.id):
        await message.reply_text(
            "В групповом чате отправлять отчеты могут только администраторы."
        )
        return END

    # Очищаем предыдущие данные
    if context.user_data:
        context.user_data.clear()

    keyboard = [
        [
            InlineKeyboardButton("📝 Поиск расписания группы", callback_data="group_schedule"),
            InlineKeyboardButton("👨‍🏫 Поиск расписания преподавателя", callback_data="lecturer_schedule")
        ],
        [
            InlineKeyboardButton("📚 Поиск тех.карты", callback_data="techcard"),
            InlineKeyboardButton("❓ Другая", callback_data="other")
        ],
        [InlineKeyboardButton("🔙 Вернуться на старт", callback_data="start")]
    ]
    
    await message.reply_text(
        "Если вы обнаружили ошибки, выберите одну из этих категорий:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CATEGORY_SELECTION

async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not (query := update.callback_query):
        return END
    
    await query.answer()
    
    # Очищаем существующие данные
    if context.user_data:
        context.user_data.clear()  # Очищаем существующие данные
    
    # Добавляем новые данные
    context.user_data['report_category'] = query.data
    
    try:
        if not query.message:
            return END
            
        if query.data == 'start':
            await query.message.edit_text("Вы вернулись в главное меню.")
            context.user_data.clear()  # Очищаем данные при выходе
            return END
            
        if query.data == 'group_schedule':
            await query.message.edit_text("Введите номер вашей группы:")
            return GROUP_INPUT
            
        if query.data == 'lecturer_schedule':
            await query.message.edit_text("Введите Фамилию преподавателя:")
            return LECTURER_INPUT
            
        if query.data == 'techcard':
            await query.message.edit_text("Введите номер вашей группы:")
            return TECHCARD_GROUP
            
        if query.data == 'other':
            await query.message.edit_text(
                "Введите сообщение для администраторов и постарайтесь объяснить проблему:"
            )
            return MESSAGE_INPUT
            
        return END
        
    except Exception as e:
        logging.error(f"Ошибка при обработке категории: {e}")
        await query.message.edit_text("Произошла ошибка. Попробуйте позже.")
        return END

async def group_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода группы"""
    if not update.message or not update.message.text:
        return END
        
    if not context.user_data:
        context.user_data = {}
        
    context.user_data['group'] = update.message.text
    await update.message.reply_text(
        "Введите сообщение для администраторов и постарайтесь объяснить проблему:"
    )
    return MESSAGE_INPUT

async def lecturer_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода преподавателя"""
    if not update.message or not update.message.text:
        return END
        
    if not context.user_data:
        context.user_data = {}
        
    context.user_data['lecturer'] = update.message.text
    await update.message.reply_text(
        "Введите сообщение для администраторов и постарайтесь объяснить проблему:"
    )
    return MESSAGE_INPUT

async def techcard_group_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода группы для техкарты"""
    if not update.message or not update.message.text:
        return END
        
    if not context.user_data:
        context.user_data = {}
        
    context.user_data['group'] = update.message.text
    await update.message.reply_text(
        "Если ошибка в том, что ссылка не верна или не актуальна. Введите ссылку на актуальную карту:",
        reply_markup=NOT_LINK_KEYBOARD
    )
    return TECHCARD_LINK

async def techcard_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода ссылки на техкарту"""
    if not context.user_data:
        context.user_data = {}
        
    if update.callback_query:
        await update.callback_query.answer()
        context.user_data['techcard_link'] = None
        await update.callback_query.message.edit_text(
            "Введите сообщение для администраторов и постарайтесь объяснить проблему:"
        )
    elif update.message and update.message.text:
        context.user_data['techcard_link'] = update.message.text
        await update.message.reply_text(
            "Введите сообщение для администраторов и постарайтесь объяснить проблему:"
        )
    else:
        return END
        
    return MESSAGE_INPUT

async def message_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода сообщения"""
    if not update.message or not update.message.text:
        return END
        
    if not context.user_data:
        context.user_data = {}
        
    context.user_data['message'] = update.message.text
    await update.message.reply_text(
        "Подтвердите отправку отчета:",
        reply_markup=CONFIRM_KEYBOARD
    )
    return CONFIRM_SEND

async def send_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отправка отчета"""
    if not (query := update.callback_query) or not query.message:
        return END
        
    await query.answer()
    
    if not (user := query.from_user):
        await query.message.edit_text("Произошла ошибка при отправке отчета.")
        return END
        
    if not context.user_data:
        await query.message.edit_text("Произошла ошибка. Попробуйте начать сначала.")
        return END
        
    try:
        category = context.user_data.get('report_category')
        message = context.user_data.get('message')
        
        if not all([category, message]):
            await query.message.edit_text("Произошла ошибка. Попробуйте начать сначала.")
            return END
        
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
        
    except Exception as e:
        logging.error(f"Ошибка при отправке отчета: {e}")
        await query.message.edit_text("Произошла ошибка при отправке отчета.")
        return END

async def admin_report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик действий администратора по отчету"""
    if not (query := update.callback_query):
        return
        
    user_id = update.effective_user.id
    if not await check_admin_rights(update, user_id, 'can_manage_reports'):
        await query.answer("У вас нет прав для упрвления отчетами")
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
                text="❌ Вам ограничен доступ к отправке отчето об ошибках."
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

async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик отмены отправки отчета"""
    if update.message:
        await update.message.reply_text("Отправка отчета отменена.")
    if context.user_data:
        context.user_data.clear()
    return END

report_handler = ConversationHandler(
    entry_points=[CommandHandler('report', report_callback)],
    states={
        CATEGORY_SELECTION: [
            CallbackQueryHandler(category_handler, pattern="^(group_schedule|lecturer_schedule|techcard|other|start)$")
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
    fallbacks=[MessageHandler(filters.COMMAND, cancel_report)],
    per_message=False,
    per_user=True,
    per_chat=True,
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
        
    if user.id not in BOT_ADMIN_IDS:
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