from telegram import Message
from telegrambot.common.decorator import message_update_handler
from telegrambot.context import ApplicationContext

@message_update_handler
async def start_callback(update: Message, _context: ApplicationContext) -> None:
    """Обработчик команды /start"""
    await update.reply_html(
        f"Привет, {update.from_user.mention_html()}! Это бот для поиск расписания студентов и преподавателей АлтГУ.\n"
        + "Используй контекстное меню или команды для взаимодействия с ботом.\n"
        + "Если возникли ошибки или есть идеи, напиши нам.\n"
        + "Контакты в описании бота")