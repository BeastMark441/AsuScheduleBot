from .common import *

async def cleansavelect_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    saved_lecturer = DATABASE.get_lecturer(user_id)
    if saved_lecturer:
        DATABASE.clear_lecturer(user_id)
        await update.message.reply_text(f"Сохраненный преподаватель {saved_lecturer} удален.")
    else:
        await update.message.reply_text("У вас нет сохраненного преподавателя.")        
