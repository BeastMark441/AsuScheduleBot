from datetime import datetime, timedelta
from typing import Dict, List, Optional
from telegram.helpers import escape_markdown

def format_schedule(timetable_data: Dict, schedule_link: str, group_name: str, target_date: Optional[datetime] = None) -> str:
    # Формируем заголовок расписания
    formatted_schedule = [f"📚 Расписание для группы: {escape_markdown(group_name, version=2)}\n"]
    
    days = timetable_data.get("days", [])
    if not days:
        # Если нет данных о днях, добавляем сообщение об отсутствии расписания
        formatted_schedule.append("Расписание не найдено или нет занятий на указанный период\\.")
    else:
        # Определяем начало и конец недели для target_date
        start_of_week = target_date - timedelta(days=target_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        for day in days:
            date = datetime.strptime(day["date"], "%Y-%m-%d")
            if start_of_week <= date <= end_of_week:
                # Форматируем дату и добавляем ее в расписание
                formatted_date = date.strftime('%d\\.%m')  # Экранируем точку
                formatted_schedule.append(f"📅 {get_weekday(date.weekday())} {formatted_date}\n")
                
                lessons = day.get("lessons", [])
                if not lessons:
                    formatted_schedule.append("Нет занятий\n")
                else:
                    # Форматируем каждое занятие и добавляем в расписание
                    for lesson in lessons:
                        formatted_lesson = format_lesson(lesson)
                        formatted_schedule.append(formatted_lesson)
                formatted_schedule.append("")  # Пустая строка между днями
    
    # Добавляем ссылку на полное расписание
    escaped_link = schedule_link.replace(".", "\\.")
    formatted_schedule.append(f"🚀 [Ссылка на расписание]({escaped_link})")
    
    return "\n".join(formatted_schedule)

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
