import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import TelegramError
from telegram.constants import ParseMode
from .common import DATABASE
from functools import lru_cache
from typing import Set
from config import BOT_ADMIN_IDS, AdminRights, check_admin_rights

# Кэшируем результаты на 5 минут
@lru_cache(maxsize=1, typed=False)
def get_chat_ids() -> Set[int]:
    users = DATABASE.get_all_users()
    return {user[0] for user in users}

async def check_admin_rights(update: Update, user_id: int, required_right: str) -> bool:
    """
    Проверяет права администратора
    update: Update объект от телеграма
    user_id: ID пользователя
    required_right: Требуемое право (например, 'can_broadcast')
    """
    # Если пользователь является администратором бота - у него есть все права
    if user_id in BOT_ADMIN_IDS:
        return AdminRights.BOT_ADMIN.get(required_right, False)
        
    # Проверяем, является ли пользователь администратором чата
    if update.effective_chat and update.effective_chat.type != 'private':
        try:
            member = await update.effective_chat.get_member(user_id)
            is_chat_admin = member.status in ['creator', 'administrator']
            if is_chat_admin:
                return AdminRights.CHAT_ADMIN.get(required_right, False)
        except Exception:
            return False
            
    return False

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /admin
    Отправляет сообщение во все активные чаты бота
    Использование: /admin <текст сообщения>
    """
    if not ((message := update.message) and (user := update.effective_user)):
        return
        
    if not await check_admin_rights(update, user.id, 'can_broadcast'):
        await message.reply_text("У вас нет прав для использования этой команды.")
        return
    
    # Если команда /admin без аргументов - показываем статистику
    if not context.args:
        users = DATABASE.get_all_users()
        stats = (
            f"📊 <b>Статистика бота:</b>\n\n"
            f"👥 Всего пользователей: {len(users)}\n\n"
            f"📚 С сохраненной группой: {sum(1 for u in users if u[1])}\n\n"
            f"👨‍🏫 С сохраненным преподавателем: {sum(1 for u in users if u[2])}"
        )
        await message.reply_text(stats, parse_mode=ParseMode.HTML)
        return

    broadcast_message = ' '.join(context.args)
    
    # Заменяем \n на реальные переносы строк
    broadcast_message = broadcast_message.replace('\\n', '\n')
    
    # Форматируем сообщение для рассылки
    formatted_message = (
        f"📢 <b>Сообщение от администрации</b>\n"
        f"{'─' * 32}\n\n"
        f"{broadcast_message}\n\n"
        f"{'─' * 32}\n"
        f"<i>С уважением,\nадминистрация бота</i>"
    )
    
    # Создаем клавиатуру для подтверждения
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"broadcast_confirm_{user.id}"),
            InlineKeyboardButton("❌ Отменить", callback_data=f"broadcast_cancel_{user.id}")
        ]
    ]
    
    # Сохраняем сообщение для рассылки
    if not context.user_data:
        context.user_data.clear()
    context.user_data.update({'broadcast_message': formatted_message})
    
    # Отправляем предпросмотр с запросом подтверждения
    preview = (
        f"<b>Предпросмотр сообщения для рассылки:</b>\n\n"
        f"{formatted_message}\n\n"
        f"Отправить это сообщение всем пользователям?"
    )
    
    await message.reply_text(
        preview,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик подтверждения рассылки"""
    if not (query := update.callback_query):
        return
        
    await query.answer()
    
    action, admin_id = query.data.split('_')[1:]
    if int(admin_id) != update.effective_user.id:
        await query.answer("Это действие доступно только инициатору рассылки", show_alert=True)
        return
        
    if action == 'cancel':
        await query.message.edit_text("❌ Рассылка отменена.")
        if context.user_data:
            context.user_data.pop('broadcast_message', None)
        return
        
    if not context.user_data or 'broadcast_message' not in context.user_data:
        await query.message.edit_text("❌ Ошибка: сообщение для рассылки не найдено.")
        return
        
    broadcast_message = context.user_data['broadcast_message']
    try:
        chat_ids = get_chat_ids()
        
        if not chat_ids:
            await query.message.edit_text("Нет активных пользователей для рассылки.")
            return

        successful = failed = 0
        
        # Используем asyncio.gather для параллельной отправки сообщений
        tasks = []
        for chat_id in chat_ids:
            task = context.bot.send_message(
                chat_id=chat_id,
                text=broadcast_message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                failed += 1
                logging.error(f"Ошибка отправки: {result}")
            else:
                successful += 1
        
        # Отправляем статистику рассылки
        stats = (
            f"📊 <b>Статистика рассылки:</b>\n\n"
            f"✅ Успешно отправлено: {successful}\n"
            f"❌ Ошибок отправки: {failed}\n"
            f"👥 Всего пользователей: {len(chat_ids)}"
        )
        
        await query.message.edit_text(
            stats,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logging.error(f"Ошибка при рассылке: {e}")
        await query.message.edit_text(
            "❌ <b>Произошла ошибка при выполнении рассылки.</b>\n"
            f"Подробности: <code>{str(e)}</code>",
            parse_mode=ParseMode.HTML
        )
    finally:
        if context.user_data:
            context.user_data.pop('broadcast_message', None)

async def send_to_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /send_to
    Отправляет сообщение конкретному пользователю от имени бота
    Использование: /send_to <user_id> <текст сообщения>
    """
    if not ((message := update.message) and (user := update.effective_user)):
        return
        
    if not await check_admin_rights(update, user.id, 'can_send_to'):
        await message.reply_text("У вас нет прав для использования этой команды.")
        return
    
    if not context.args or len(context.args) < 2:
        usage_text = (
            "ℹ️ <b>Использование команды:</b>\n\n"
            "/send_to <code>user_id</code> <code>текст сообщения</code>\n\n"
            "📝 <b>Пример:</b>\n"
            "/send_to 123456789 Здравствуйте! Ваша проблема решена.\n\n"
            "💡 <b>Примечания:</b>\n"
            "• Можно использовать HTML-разметку\n"
            "• Поддерживаются эмодзи\n"
            "• Для переноса строки используйте \\n"
        )
        await message.reply_text(usage_text, parse_mode=ParseMode.HTML)
        return
        
    try:
        target_user_id = int(context.args[0])
        text_message = ' '.join(context.args[1:])
        
        # Заменяем \n на реальные переносы строк
        text_message = text_message.replace('\\n', '\n')
        
        # Форматируем сообщение
        formatted_message = (
            f"📬 <b>Сообщение от администрации</b>\n"
            f"{'─' * 32}\n\n"
            f"{text_message}\n\n"
            f"{'─' * 32}\n"
            f"<i>С уважением,\nадминистрация бота</i>"
        )
        
        # Проверяем, существует ли пользователь в базе
        users = DATABASE.get_all_users()
        if not any(user[0] == target_user_id for user in users):
            await message.reply_text(
                f"❌ Пользователь с ID {target_user_id} не найден в базе данных."
            )
            return
        
        # Отправляем сообщение
        sent_message = await context.bot.send_message(
            chat_id=target_user_id,
            text=formatted_message,
            parse_mode=ParseMode.HTML
        )
        
        # Отправляем подтверждение администратору
        confirmation = (
            f"✅ <b>Сообщение успешно отправлено</b>\n\n"
            f"👤 Получатель: <code>{target_user_id}</code>\n"
            f"📝 Текст сообщения:\n\n"
            f"{formatted_message}"
        )
        
        await message.reply_text(
            confirmation,
            parse_mode=ParseMode.HTML
        )
        
    except ValueError:
        await message.reply_text(
            "❌ <b>Ошибка:</b> Некорректный ID пользователя.\n"
            "ID должен быть целым числом.",
            parse_mode=ParseMode.HTML
        )
    except TelegramError as e:
        error_msg = (
            f"❌ <b>Ошибка при отправке сообщения</b>\n\n"
            f"👤 Пользователь: <code>{target_user_id}</code>\n"
            f"⚠️ Причина: <code>{str(e)}</code>"
        )
        logging.error(f"Ошибка при отправке сообщения пользователю {target_user_id}: {e}")
        await message.reply_text(
            error_msg,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logging.error(f"Неожиданная ошибка при отправке сообщения: {e}")
        await message.reply_text(
            "❌ <b>Произошла неожиданная ошибка</b>\n"
            f"Подробности: <code>{str(e)}</code>",
            parse_mode=ParseMode.HTML
        )

# Создаем обработчики команд
admin_handler = CommandHandler("admin", admin_callback)
send_to_handler = CommandHandler("send_to", send_to_callback)
broadcast_handler = CallbackQueryHandler(
    broadcast_callback,
    pattern="^broadcast_(confirm|cancel)_[0-9]+$"
) 