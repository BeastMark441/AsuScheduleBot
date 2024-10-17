import asyncio

from telegram import Update
from telegram.ext import ContextTypes

import asu.schedule as asu

async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) == 0:
        await update.message.reply_text('Пожалуйста, введите название группы. Например: /schedule 305с11-4')
        return

    group_name = context.args[0]
    await update.message.reply_text(text=f'Ищу расписание для группы: {group_name}...')

    schedule_url = asu.find_group_url(group_name)

    await asyncio.sleep(1)

    if schedule_url:
        response_text = asu.get_timetable(schedule_url)  # Запускаем в отдельном потоке
        if isinstance(response_text, str) and "Ошибка" in response_text:
            await update.message.reply_text(response_text)
        else:
            formatted_timetable = asu.format_schedule(response_text, schedule_url, group_name)
            await update.message.reply_text(formatted_timetable, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text("Ошибка получении группы")