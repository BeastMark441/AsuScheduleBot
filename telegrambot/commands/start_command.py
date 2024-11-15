from telegram import Update
from telegram.ext import ContextTypes


async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    if ((message := update.message) and (user := message.from_user)):
        await message.reply_html(
        f"Привет, {user.mention_html()}! Это бот для поиск расписания студентов и преподавателей АлтГУ.\n"
        + "Используй контекстное меню или команды для взаимодействия с ботом.\n"
        + "Если возникли ошибки или есть идеи, напиши нам.\n"
        + "Контакты в описании бота")