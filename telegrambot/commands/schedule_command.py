from datetime import timedelta
import typing
from typing import Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, User
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

import asu
from asu.group import Group
from .common import *


async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /schedule"""
    
    if not ((message := update.message) and (user := message.from_user)):
        return END
    
    # В групповых чатах сохранение группы доступно только администраторам
    is_group_chat = message.chat.type != 'private'
    can_save = await check_group_permissions(update, user.id)
    
    group_name: str
    
    if context.args:
        group_name = ''.join(context.args)
    elif (group_name := DATABASE.get_group(user.id) if not is_group_chat else None):
        await update.message.reply_text(f"Используется сохраненная группа: {group_name}")
    else:
        await update.message.reply_text(
            "Введите название группы:" if can_save else 
            "В групповом чате необходимо указывать группу после команды, например: /schedule 305с11-4"
        )
        return GET_GROUP_NAME if can_save else END
    
    return await handle_schedule(update, context, group_name)

async def get_group_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода названия группы"""
    
    if not ((message := update.message) and (group_name := message.text)):
        return END
    
    if not group_name:
        _ = await message.reply_text("Пожалуйста, введите корректное название группы")
        return GET_GROUP_NAME
    
    return await handle_schedule(update, context, group_name)

async def handle_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, group_name: str) -> int:
    """Основной обработчик запроса расписания"""
    message = typing.cast(Message, update.message)
    user_data = typing.cast(dict[Any, Any], context.user_data)
    user = typing.cast(User, message.from_user)
    
    schedule = await asu.find_schedule_url(group_name)
    if not schedule:
        await message.reply_text("Ошибка получения группы. Пожалуйста, проверьте название и попробуйте снова")
        return END
    
    user_data[SELECTED_SCHEDULE] = schedule
    
    if not DATABASE.get_group(user.id):
        return await ask_to_save_group(update, context, schedule.name)
    
    return await show_schedule_options(update, context)

async def ask_to_save_group(update: Update, context: ContextTypes.DEFAULT_TYPE, group_name: str) -> int:
    """Запрос на сохранение группы"""
    message = typing.cast(Message, update.message)
    keyboard = [
        [InlineKeyboardButton("Да", callback_data="save_yes"),
         InlineKeyboardButton("Нет", callback_data="save_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text(
        f"Хотите ли вы сохранить группу {group_name} для быстрого доступа в будущем?",
        reply_markup=reply_markup)
    return SAVE_GROUP

async def save_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ответа на запрос сохранения группы"""
    if not (query := update.callback_query):
        return END
    
    await query.answer()

    if query.data == "save_yes":
        schedule = context.user_data.get(SELECTED_SCHEDULE)
        if isinstance(schedule, Group):
            user_id = update.effective_user.id
            DATABASE.save_group(user_id, schedule.name)
            await query.edit_message_text(f"Группа {schedule.name} сохранена.")
        else:
            await query.edit_message_text("Произошла ошибка при сохранении группы.")

    return await show_schedule_options(update, context)

async def show_schedule_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать опции выбора периода расписания"""
    keyboard = [
        [InlineKeyboardButton("Сегодня", callback_data="T")],
        [InlineKeyboardButton("Завтра", callback_data="M")],
        [InlineKeyboardButton("На эту неделю", callback_data="W")],
        [InlineKeyboardButton("На следующую неделю", callback_data="NW")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    schedule: Group = context.user_data[SELECTED_SCHEDULE]
    await update.effective_message.reply_text(
            f"📚 Группа {schedule.name}\nВыберите, на какой день хотите получить расписание:",
            reply_markup=reply_markup)
    
    return SHOW_SCHEDULE
        
schedule_handler = ConversationHandler(
    entry_points=[CommandHandler("schedule", schedule_callback)],
    states={
        GET_GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group_name)],
        SAVE_GROUP: [CallbackQueryHandler(save_group_callback, pattern='^save_yes|save_no$')],
        SHOW_SCHEDULE: [
            CallbackQueryHandler(handle_show_schedule, pattern='^T|M|W|NW$')
        ]
    },
    fallbacks=[MessageHandler(filters.COMMAND, cancel_conversation)],
    allow_reentry=True,
    per_message=False,
    per_user=True,
    per_chat=True,
    name="schedule_conversation"
)