from telegram import Update
from telegram.ext import ContextTypes
from .common import DATABASE

async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    if not ((message := update.message) and (user := message.from_user)):
        return

    # Сохраняем информацию о пользователе при первом использовании
    DATABASE.save_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    await message.reply_html(
        f"Привет, {user.mention_html()}! Это бот для поиска расписания студентов и преподавателей АлтГУ.\n"
        "Используй контекстное меню или команды для взаимодействия с ботом.\n"
        "Если возникли ошибки или есть идеи, напиши нам.\n"
        "Контакты в описании бота"
    )