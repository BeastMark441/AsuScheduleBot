import asyncio
import telegram
from telegram import CallbackQuery, ForceReply, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler

import asu.schedule as asu

GET_GROUP_NAME = 1
CONTEXT_GROUP = 'group'

async def get_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[CONTEXT_GROUP] = update.message.text
    await __showSchedule(update, context)
    return ConversationHandler.END

async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    await update.message.reply_html(
        f"Привет, {user.mention_html()}! Это бот для поиска расписания студентов и преподавателей АлтГУ.\n"
        "Если возникли ошибки или есть идеи, напиши нам.\n"
        "Контакты в описании бота")


async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get(CONTEXT_GROUP, None) and (context.args is None or len(context.args) == 0):
        await update.message.reply_text('Пожалуйста, введите название группы:', reply_markup=ForceReply(True))
        return GET_GROUP_NAME

    await __showSchedule(update, context)

    return ConversationHandler.END

async def __showSchedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_name: str = ""
    if context.args is not None and len(context.args) > 0:
        group_name = ''.join(context.args)
    elif context.user_data is not None and context.user_data.get(CONTEXT_GROUP) is not None:
        group_name = context.user_data[CONTEXT_GROUP]

    message = await update.message.reply_text(text=f'Ищу расписание для группы: {group_name}...')

    schedule_url = await asyncio.to_thread(asu.find_schedule_url, group_name)

    if schedule_url:
        # Ждём секунду между вызовами, так как ASU кидает 429 ошибку
        await asyncio.sleep(1)

        response_text = await asyncio.to_thread(asu.get_timetable, schedule_url)
        if isinstance(response_text, str) and "Ошибка" in response_text:
            await message.edit_text(response_text)
        else:
            formatted_timetable = asu.format_schedule(response_text, schedule_url, group_name)
            await message.edit_text(formatted_timetable, parse_mode=telegram.constants.ParseMode.MARKDOWN_V2)
    else:
        await message.edit_text(f"Группа {group_name} не существует")
