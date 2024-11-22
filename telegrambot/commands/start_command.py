from telegram import Update
from telegram.ext import ContextTypes
from .common import DATABASE

async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    if not ((message := update.message) and (user := message.from_user)):
        return

    # Сохраняем ID и username пользователя при первом использовании
    DATABASE.save_user(user.id, user.username)

    await message.reply_html(
        f"Привет, {user.mention_html()}! Это бот для поиска расписания студентов и преподавателей АлтГУ.\n"
        "Используй контекстное меню или команды для взаимодействия с ботом.\n"
        "Если возникли ошибки или есть идеи, напиши нам.\n"
        "Контакты в описании бота"
    )