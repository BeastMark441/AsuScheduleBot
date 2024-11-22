import logging
import asyncio
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.error import TelegramError
from telegram.constants import ParseMode
from .common import DATABASE
from functools import lru_cache
from typing import Set
from config import ADMIN_IDS

# Кэшируем результаты на 5 минут
@lru_cache(maxsize=1, typed=False)
def get_chat_ids() -> Set[int]:
    users = DATABASE.get_all_users()
    return {user[0] for user in users}

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /admin
    Отправляет сообщение во все активные чаты бота
    Использование: /admin <текст сообщения>
    """
    if not ((message := update.message) and (user := update.effective_user)):
        return
        
    if user.id not in ADMIN_IDS:
        await message.reply_text("У вас нет прав для использования этой команды.")
        return
    
    # Если команда /admin без аргументов - показываем статистику
    if not context.args:
        users = DATABASE.get_all_users()
        stats = (
            f"📊 Статистика бота:\n"
            f"Всего пользователей: {len(users)}\n"
            f"С сохраненной группой: {sum(1 for u in users if u[1])}\n"
            f"С сохраненным преподавателем: {sum(1 for u in users if u[2])}"
        )
        await message.reply_text(stats)
        return

    broadcast_message = ' '.join(context.args)
    
    try:
        chat_ids = get_chat_ids()  # Используем кэшированную функцию
        
        if not chat_ids:
            await message.reply_text("Нет активных пользователей для рассылки.")
            return

        successful = failed = 0
        
        # Используем asyncio.gather для параллельной отправки сообщений
        tasks = []
        for chat_id in chat_ids:
            task = context.bot.send_message(
                chat_id=chat_id,
                text="📢 Сообщение от администрации:\n\n" + broadcast_message,
                parse_mode=ParseMode.HTML
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                failed += 1
                logging.error(f"Ошибка отправки: {result}")
            else:
                successful += 1
        
        await message.reply_text(
            f"✅ Успешно отправлено: {successful}\n"
            f"❌ Ошибок отправки: {failed}\n"
            f"📊 Всего пользователей: {len(chat_ids)}"
        )
        
    except Exception as e:
        logging.error(f"Ошибка при рассылке: {e}")
        await message.reply_text("Произошла ошибка при выполнении рассылки.")

async def send_to_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /send_to
    Отправляет сообщение конкретному пользователю от имени бота
    Использование: /send_to <user_id> <текст сообщения>
    """
    if not ((message := update.message) and (user := update.effective_user)):
        return
        
    if user.id not in ADMIN_IDS:
        await message.reply_text("У вас нет прав для использования этой команды.")
        return
    
    if not context.args or len(context.args) < 2:
        await message.reply_text(
            "Использование: /send_to <user_id> <текст сообщения>\n"
            "Пример: /send_to 123456789 Здравствуйте, ваша проблема решена!"
        )
        return
        
    try:
        target_user_id = int(context.args[0])
        text_message = ' '.join(context.args[1:])
        
        # Проверяем, существует ли пользователь в базе
        users = DATABASE.get_all_users()
        if not any(user[0] == target_user_id for user in users):
            await message.reply_text(f"Пользователь с ID {target_user_id} не найден в базе данных.")
            return
        
        # Отправляем сообщение
        await context.bot.send_message(
            chat_id=target_user_id,
            text=text_message,
            parse_mode=ParseMode.HTML
        )
        
        await message.reply_text(f"✅ Сообщение успешно отправлено пользователю {target_user_id}")
        
    except ValueError:
        await message.reply_text("Некорректный ID пользователя.")
    except TelegramError as e:
        error_msg = f"Ошибка при отправке сообщения пользователю {target_user_id}: {str(e)}"
        logging.error(error_msg)
        await message.reply_text(error_msg)
    except Exception as e:
        logging.error(f"Неожиданная ошибка при отправке сообщения: {e}")
        await message.reply_text("Произошла ошибка при отправке сообщения.")

# Создаем обработчики команд
admin_handler = CommandHandler("admin", admin_callback)
send_to_handler = CommandHandler("send_to", send_to_callback) 