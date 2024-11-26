from .common import *

async def cleansavelect_callback(update: Update, _context: ApplicationContext) -> None:
    
    saved_lecturer = await get_saved_lecturer(update.effective_user)
    if saved_lecturer:
        await set_saved_lecturer(update.effective_user, None)
        await update.message.reply_text(f"Сохраненный преподаватель {saved_lecturer.name} удален.")
    else:
        await update.message.reply_text("У вас нет сохраненного преподавателя.")
