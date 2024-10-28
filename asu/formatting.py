from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from telegram.helpers import escape_markdown
import logging

def format_schedule(timetable_data: Dict, schedule_link: str, group_name: str, target_date: Optional[Union[datetime, 'ScheduleRequest']] = None) -> str:
    logging.info(f"Форматирование расписания для группы {group_name}. Данные: {timetable_data}")
    
    # Формируем заголовок расписания
    formatted_schedule = [f"📚 Расписание для группы: {escape_markdown(group_name, version=2)}\n"]
    
    days = timetable_data.get("days", [])
    if not days:
        logging.warning(f"Нет данных о днях в расписании для группы {group_name}")
        formatted_schedule.append("На указанный период занятий не найдено\\.")
    else:
        # Определяем период для фильтрации
        if target_date:
            if hasattr(target_date, 'is_week_request') and target_date.is_week_request:
                # Для недельного запроса используем всю неделю
                start_of_week = target_date.date - timedelta(days=target_date.date.weekday())
                end_of_week = start_of_week + timedelta(days=6)
                logging.info(f"Фильтруем по периоду недели: {start_of_week} - {end_of_week}")
            else:
                # Для конкретного дня используем только этот день
                if hasattr(target_date, 'date'):
                    start_of_week = end_of_week = target_date.date
                else:
                    start_of_week = end_of_week = target_date
                logging.info(f"Фильтруем по конкретной дате: {start_of_week}")
        else:
            # Если дата не указана, показываем все дни
            start_of_week = end_of_week = None
            logging.info("Дата не указана, показываем все дни")
        
        found_lessons = False
        # Сортируем дни по дате
        sorted_days = sorted(days, key=lambda x: x["date"])
        
        for day in sorted_days:
            date = datetime.strptime(day["date"], "%Y-%m-%d")
            
            # Проверяем, попадает ли день в указанный период
            if start_of_week and end_of_week:
                if isinstance(start_of_week, datetime):
                    start_date = start_of_week.date()
                    end_date = end_of_week.date()
                else:
                    start_date = start_of_week
                    end_date = end_of_week
                
                if not (start_date <= date.date() <= end_date):
                    logging.debug(f"Пропускаем день {date.date()}, не входит в период {start_date} - {end_date}")
                    continue
            
            found_lessons = True
            formatted_date = date.strftime('%d\\.%m')
            formatted_schedule.append(f"📅 {get_weekday(date.weekday())} {formatted_date}\n")
            
            lessons = day.get("lessons", [])
            if not lessons:
                formatted_schedule.append("Нет занятий\n")
            else:
                # Сортируем занятия по номеру пары
                sorted_lessons = sorted(lessons, key=lambda x: int(x.get("number", "0")))
                for lesson in sorted_lessons:
                    formatted_lesson = format_lesson(lesson)
                    formatted_schedule.append(formatted_lesson)
                formatted_schedule.append("")
        
        if not found_lessons:
            logging.warning(f"Не найдено занятий в указанный период для группы {group_name}")
            formatted_schedule.append("На указанный период занятий не найдено\\.")
    
    # Добавляем ссылку на полное расписание
    escaped_link = schedule_link.replace(".", "\\.")
    formatted_schedule.append(f"🚀 [Ссылка на расписание]({escaped_link})")
    
    result = "\n".join(formatted_schedule)
    logging.info(f"Сформированное расписание: {result}")
    return result

def format_lesson(lesson: Dict) -> str:
    # Извлекаем и форматируем данные о занятии
    number = lesson.get("number", "")
    time_start = lesson.get("timeStart", "").replace(":", "\\:")
    time_end = lesson.get("timeEnd", "").replace(":", "\\:")
    subject = escape_markdown(lesson.get("subject", {}).get("title", "Предмет не указан"), version=2)
    teacher = escape_markdown(lesson.get("teacher", {}).get("title", "Преподаватель не указан"), version=2)
    classroom = escape_markdown(lesson.get("classroom", {}).get("title", "Аудитория не указана"), version=2)
    
    # Формируем строку с информацией о занятии
    formatted_lesson = (
        f"{num_to_emoji(number)}🕑 {time_start} \\- {time_end}\n"
        f"📚 {subject}\n"
        f"👩 {teacher}\n"
        f"🏢 {classroom}\n"
    )
    return formatted_lesson

def get_weekday(weekday: int) -> str:
    # Возвращаем название дня недели по его номеру
    weekdays = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    return weekdays[weekday]

def num_to_emoji(num: str) -> str:
    # Конвертируем числовой номер пары в эмодзи
    emoji_numbers = ("0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣")
    if num.isdigit() and int(num) < len(emoji_numbers):
        return emoji_numbers[int(num)]
    return "❓"
