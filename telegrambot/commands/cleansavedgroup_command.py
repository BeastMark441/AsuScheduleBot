from .common import *

async def cleansavegroup_callback(update: Update, _context: ApplicationContext) -> None:
    """Обработчик команды очистки сохраненной группы"""
    
    saved_group = await get_saved_group(update.effective_user)
    if saved_group:
        await set_saved_group(update.effective_user, None)
        await update.message.reply_text(f"Сохраненная группа {saved_group} удалена.")
    else:
        await update.message.reply_text("У вас нет сохраненной группы.")
