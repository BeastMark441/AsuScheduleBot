import logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.error import TelegramError
from telegram.constants import ParseMode
from .common import DATABASE

# ID администраторов (можно вынести в конфиг или .env)
ADMIN_IDS = {983524946, 833357373, 5967050779}  # ID администраторов

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /admin
    Отправляет сообщение во все активные чаты бота
    Использование: /admin <текст сообщения>
    """
    if not ((message := update.message) and (user := update.effective_user)):
        return
        
    if user.id not in ADMIN_IDS:
        await message.reply_text(
            "У вас нет прав для использования этой команды."
        )
        return
    
    # Если команда /admin без аргументов - показываем отладочную информацию
    if not context.args:
        # Получаем информацию о текущем чате
        current_chat_info = (
            f"Текущий чат:\n"
            f"chat_id: {message.chat.id}\n"
            f"user_id: {user.id}\n"
            f"username: {user.username}\n"
        )
        
        # Получаем информацию из базы данных
        users = DATABASE.get_all_users()
        
        # Разбиваем информацию о пользователях на части
        users_info = []
        current_part = []
        
        for user in users:
            user_str = (
                f"ID: {user[0]}, "
                f"Username: {user[1] or 'нет'}, "
                f"Имя: {user[2] or 'нет'}, "
                f"Фамилия: {user[3] or 'нет'}, "
                f"Группа: {user[4] or 'нет'}, "
                f"Преподаватель: {user[5] or 'нет'}"
            )
            
            if len("\n".join(current_part + [user_str])) > 3000:  # Оставляем запас для доп. текста
                users_info.append("\n".join(current_part))
                current_part = [user_str]
            else:
                current_part.append(user_str)
                
        if current_part:
            users_info.append("\n".join(current_part))
        
        # Отправляем первое сообщение с общей информацией
        await message.reply_text(
            "Использование: /admin <текст сообщения>\n\n"
            "Отладочная информация:\n"
            f"{current_chat_info}\n"
            f"Данные из базы:\n"
            f"Всего пользователей: {len(users)}\n"
        )
        
        # Отправляем информацию о пользователях частями
        for part in users_info:
            await message.reply_text(f"Список пользователей:\n{part}")
        return

    broadcast_message = ' '.join(context.args)
    
    try:
        # Получаем всех пользователей
        users = DATABASE.get_all_users()
        chat_ids = {user[0] for user in users}  # user[0] это user_id
        
        logging.info(f"Найдено {len(chat_ids)} пользователей в базе данных")
        logging.info(f"Список ID для рассылки: {chat_ids}")
        
    except Exception as e:
        logging.error(f"Ошибка при получении ID пользователей из базы данных: {e}")
        await message.reply_text("Произошла ошибка при получении списка пользователей.")
        return
    
    if not chat_ids:
        await message.reply_text("Нет активных пользователей для рассылки.")
        return

    # Счетчики для статистики
    successful = 0
    failed = 0
    failed_ids = []

    # Отправляем сообщение в каждый чат
    for chat_id in chat_ids:
        try:
            # Добавляем пометку, что это сообщение от администрации
            formatted_message = "📢 Сообщение от администрации:\n\n" + broadcast_message
            
            logging.info(f"Отправка сообщения пользователю {chat_id}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=formatted_message,
                parse_mode=ParseMode.HTML
            )
            successful += 1
            logging.info(f"Успешно отправлено пользователю {chat_id}")
        except TelegramError as e:
            failed += 1
            failed_ids.append(chat_id)
            logging.error(f"Ошибка отправки сообщения в чат {chat_id}: {str(e)}")
    
    # Отправляем статистику администратору
    status_message = (
        f"Рассылка завершена\n"
        f"✅ Успешно отправлено: {successful}\n"
        f"❌ Ошибок отправки: {failed}\n"
        f"📊 Всего пользователей: {len(chat_ids)}\n"
        f"❌ ID с ошибками: {failed_ids if failed_ids else 'нет'}"
    )
    logging.info(status_message)
    await message.reply_text(status_message)

admin_handler = CommandHandler("admin", admin_callback) 