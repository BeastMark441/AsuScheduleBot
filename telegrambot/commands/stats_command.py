from datetime import datetime, timedelta
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes, 
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler
)

# Импортируем END из ConversationHandler
END = ConversationHandler.END

from config import check_admin_rights
from database.mariadb import MariaDB
from config.database import MARIADB_CONFIG

# Состояния
WAITING_PERIOD = 1

async def stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает статистику использования бота"""
    if not update.effective_user or not update.message:
        return END
        
    # Проверка прав доступа
    if not await check_admin_rights(update, update.effective_user.id, 'can_view_stats'):
        await update.message.reply_text("У вас нет прав для просмотра статистики.")
        return END

    # Создаем клавиатуру для выбора периода
    keyboard = [
        [InlineKeyboardButton("За сегодня", callback_data="stats_1")],
        [InlineKeyboardButton("За 3 дня", callback_data="stats_3")],
        [InlineKeyboardButton("За неделю", callback_data="stats_7")]
    ]
    
    await update.message.reply_text(
        "📊 Выберите период для просмотра статистики:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return WAITING_PERIOD

async def period_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора периода статистики"""
    if not (query := update.callback_query):
        return END
        
    await query.answer()
    
    # Получаем количество дней из callback_data
    days = int(query.data.split('_')[1])
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days-1)  # -1 потому что включаем текущий день
    
    db = MariaDB(**MARIADB_CONFIG)
    stats = db.get_daily_statistics(start_date, end_date)
    
    if not stats:
        await query.message.edit_text("Статистика пока не собрана.")
        return END
        
    period_text = {
        1: "сегодня",
        3: "за 3 дня",
        7: "за неделю"
    }
    
    message = f"📊 <b>Статистика {period_text[days]}:</b>\n\n"
    
    total_requests = 0
    total_successful = 0
    total_failed = 0
    unique_users = set()
    all_commands = {}
    all_groups = {}
    all_lecturers = {}
    
    for day_stats in stats:
        message += (
            f"<b>{day_stats['date'].strftime('%d.%m.%Y')}</b>\n"
            f"👥 Уникальных пользователей: {day_stats['unique_users']}\n"
            f"📝 Всего запросов: {day_stats['total_requests']}\n"
            f"✅ Успешных: {day_stats['successful_requests']}\n"
            f"❌ Ошибок: {day_stats['failed_requests']}\n"
            f"⏱ Среднее время ответа: {day_stats['avg_response_time']:.2f}s\n\n"
        )
        
        # Собираем общую статистику
        total_requests += day_stats['total_requests']
        total_successful += day_stats['successful_requests']
        total_failed += day_stats['failed_requests']
        
        # Собираем статистику по командам
        if day_stats['most_used_commands']:
            commands = json.loads(day_stats['most_used_commands'])
            for cmd, count in commands:
                all_commands[cmd] = all_commands.get(cmd, 0) + count
                
        # Собираем статистику по группам
        if day_stats['most_searched_groups']:
            groups = json.loads(day_stats['most_searched_groups'])
            for group, count in groups:
                all_groups[group] = all_groups.get(group, 0) + count
                
        # Собираем статистику по преподавателям
        if day_stats['most_searched_lecturers']:
            lecturers = json.loads(day_stats['most_searched_lecturers'])
            for lecturer, count in lecturers:
                all_lecturers[lecturer] = all_lecturers.get(lecturer, 0) + count
    
    # Добавляем общую статистику за период
    message += (
        f"<b>Общая статистика за период:</b>\n"
        f"📝 Всего запросов: {total_requests}\n"
        f"✅ Успешных: {total_successful}\n"
        f"❌ Ошибок: {total_failed}\n\n"
    )
    
    # Топ-5 команд за период
    if all_commands:
        message += "🔝 <b>Популярные команды:</b>\n"
        for cmd, count in sorted(all_commands.items(), key=lambda x: x[1], reverse=True)[:5]:
            message += f"/{cmd}: {count} раз\n"
        message += "\n"
    
    # Топ-5 групп за период
    if all_groups:
        message += "👥 <b>Популярные группы:</b>\n"
        for group, count in sorted(all_groups.items(), key=lambda x: x[1], reverse=True)[:5]:
            message += f"{group}: {count} раз\n"
        message += "\n"
    
    # Топ-5 преподавателей за период
    if all_lecturers:
        message += "👨‍🏫 <b>Популярные преподаватели:</b>\n"
        for lecturer, count in sorted(all_lecturers.items(), key=lambda x: x[1], reverse=True)[:5]:
            message += f"{lecturer}: {count} раз\n"
        message += "\n"
    
    # Добавляем кнопку для выбора другого периода
    keyboard = [
        [InlineKeyboardButton("📊 Выбрать другой период", callback_data="stats_new")]
    ]
    
    await query.message.edit_text(
        message, 
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return END

async def new_period_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик кнопки выбора нового периода"""
    if not (query := update.callback_query):
        return END
        
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("За сегодня", callback_data="stats_1")],
        [InlineKeyboardButton("За 3 дня", callback_data="stats_3")],
        [InlineKeyboardButton("За неделю", callback_data="stats_7")]
    ]
    
    await query.message.edit_text(
        "📊 Выберите период для просмотра статистики:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return WAITING_PERIOD

# Создаем ConversationHandler для команды stats
stats_handler = ConversationHandler(
    entry_points=[CommandHandler("stats", stats_callback)],
    states={
        WAITING_PERIOD: [
            CallbackQueryHandler(period_handler, pattern="^stats_[137]$"),
            CallbackQueryHandler(new_period_handler, pattern="^stats_new$")
        ]
    },
    fallbacks=[],
    per_message=False,
    per_user=True,
    per_chat=True,
    name="stats_conversation"
) 