from datetime import datetime, timedelta

from sqlalchemy import select, update
from telegram import Update, User
import telegram
from telegram.ext import ConversationHandler

import asu
from database.db import create_session
from telegrambot.context import ApplicationContext
from utils.daterange import DateRange

import database.models as models


END = ConversationHandler.END

# Group states
GET_GROUP_NAME, SAVE_GROUP, SHOW_SCHEDULE = range(3)
# Lecturer states
GET_LECTURER_NAME, SAVE_LECTURER, SHOW_LECTURER_SCHEDULE = range(3, 6)

async def get_saved_group(user: User | None) -> models.Group | None:
    if not user:
        return None
    
    stmt = select(models.User).where(models.User.id == user.id)
    async for session in create_session():
        async with session.begin():
            result = await session.execute(stmt)
            db_user = result.scalar()
            
            if db_user and db_user.saved_group_id:
                return await db_user.saved_group(session)
            
    return None

async def set_saved_group(user: User | None, group: models.Group | None) -> None:
    if not user:
        return
    
    group_id = group.id if group else None
    
    async for session in create_session():
        async with session.begin():
            # Check if the user exists
            existing_user_stmt = select(models.User).where(models.User.id == user.id)
            result = await session.execute(existing_user_stmt)
            existing_user = result.scalar_one_or_none()

            if existing_user:
                # Update the existing user's saved_group_id
                stmt = update(models.User).where(models.User.id == user.id).values(saved_group_id=group_id)
                await session.execute(stmt)
            else:
                session.add(models.User(id=user.id, saved_group_id=group_id, saved_lecturer_id=None))
                await session.commit()
                
async def get_saved_lecturer(user: User | None) -> models.Lecturer | None:
    if not user:
        return None
    
    stmt = select(models.User).where(models.User.id == user.id)
    async for session in create_session():
        async with session.begin():
            result = await session.execute(stmt)
            db_user = result.scalar()
            
            if db_user and db_user.saved_lecturer_id:
                return await db_user.saved_lecturer(session)

    return None

async def set_saved_lecturer(user: User | None, lecturer: models.Lecturer | None) -> None:
    if not user:
        return
    
    lecturer_id = lecturer.id if lecturer else None
    
    async for session in create_session():
        async with session.begin():
            # Check if the user exists
            existing_user_stmt = select(models.User).where(models.User.id == user.id)
            result = await session.execute(existing_user_stmt)
            existing_user = result.scalar_one_or_none()

            if existing_user:
                # Update the existing user's saved_group_id
                stmt = update(models.User).where(models.User.id == user.id).values(saved_lecturer_id=lecturer_id)
                await session.execute(stmt)
            else:
                session.add(models.User(id=user.id, saved_group_id=None, saved_lecturer_id=lecturer_id))
                await session.commit()
                
                
async def add_statistics(user: User | None, search_type: models.SearchType, search_query: str):
    async for session in create_session():
        async with session.begin():
            session.add(models.Stat(user_id=user.id,
                        search_type=search_type,
                        search_query=search_query,
                        timestamp=datetime.now()
                        ))
            await session.commit()

async def handle_show_schedule(update: Update, context: ApplicationContext) -> int:
    """Обработчик показа расписания"""
    if not update.callback_query:
        return END

    query = update.callback_query
    await query.answer()

    today = datetime.now()
    
    if query.data == 'T': # Today
        target_date = DateRange(today)
    elif query.data == 'M': # Tomorrow
        target_date = DateRange(today + timedelta(days=1))
    elif query.data == 'W': # This Week
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        target_date = DateRange(week_start, week_end)
    else:  # Next Week
        next_week_start = today + timedelta(days=7-today.weekday())
        next_week_end = next_week_start + timedelta(days=6)
        target_date = DateRange(next_week_start, next_week_end)

    selected_schedule: models.Lecturer | models.Group | None = context.user_data.selected_schedule
    assert selected_schedule
    is_lecturer = isinstance(selected_schedule, models.Lecturer)  # Определяем тип расписания

    timetable = await asu.client.get_schedule(selected_schedule, target_date)
    formatted_timetable = asu.format_schedule(
        timetable,
        selected_schedule.schedule_url,
        selected_schedule.name,
        target_date,
        is_lecturer  # Передаем флаг is_lecturer
    )

    timetable = await asu.client.get_schedule(selected_schedule, target_date)
    formatted_timetable = asu.format_schedule(
        timetable,
        selected_schedule.schedule_url,
        selected_schedule.name,
        target_date,
        is_lecturer
    )

    await query.edit_message_text(
        formatted_timetable, 
        parse_mode=telegram.constants.ParseMode.HTML
    )

    return END

async def exit_conversation(_update: Update, context: ApplicationContext) -> int:
    if context.user_data:
        context.user_data.clear()
    return END