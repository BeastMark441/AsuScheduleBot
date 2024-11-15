from .common import *


async def cleansavegroup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды очистки сохраненной группы"""
    user_id = update.message.from_user.id
    saved_group = DATABASE.get_group(user_id)
    if saved_group:
        DATABASE.clear_group(user_id)
        await update.message.reply_text(f"Сохраненная группа {saved_group} удалена.")
    else:
        await update.message.reply_text("У вас нет сохраненной группы.")