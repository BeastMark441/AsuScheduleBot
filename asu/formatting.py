from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from telegram.helpers import escape_markdown
import logging
from .schedule import ScheduleRequest  # Добавляем импорт ScheduleRequest

class ScheduleFormatter:
    """Класс для форматирования расписания"""
    
    def __init__(self, is_lecturer: bool = False):
        self.is_lecturer = is_lecturer
        self.emoji_numbers = ("0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣")
        self.weekdays = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

    def format_schedule(self, timetable_data: Dict, schedule_link: str, name: str, 
                       target_date: Optional[Union[datetime, 'ScheduleRequest']] = None) -> str:
        """Форматирует расписание в текстовый вид"""
        logging.info(f"Форматирование расписания для {'преподавателя' if self.is_lecturer else 'группы'} {name}")
        
        # Формируем заголовок
        header_emoji = "👩‍🏫" if self.is_lecturer else "📚"
        header_text = "преподавателя" if self.is_lecturer else "группы"
        formatted_schedule = [f"{header_emoji} Расписание {header_text}: {escape_markdown(name, version=2)}\n"]
        
        days = timetable_data.get("days", [])
        if not days:
            formatted_schedule.append("На указанный период занятий не найдено\\.")
            return self._add_schedule_link(formatted_schedule, schedule_link)
        
        # Определяем период для фильтрации
        date_range = self._get_date_range(target_date)
        if not date_range:
            return self._add_schedule_link(formatted_schedule, schedule_link)
            
        # Форматируем дни
        found_lessons = self._format_days(days, date_range, formatted_schedule)
        
        if not found_lessons:
            formatted_schedule.append("На указанный период занятий не найдено\\.")
            
        return self._add_schedule_link(formatted_schedule, schedule_link)

    def _get_date_range(self, target_date: Optional[Union[datetime, 'ScheduleRequest']]) -> Optional[tuple]:
        """Определяет диапазон дат для фильтрации"""
        if not target_date:
            return None
            
        if hasattr(target_date, 'is_week_request') and target_date.is_week_request:
            start_date = target_date.date - timedelta(days=target_date.date.weekday())
            end_date = start_date + timedelta(days=6)
            logging.info(f"Фильтруем по периоду недели: {start_date} - {end_date}")
        else:
            start_date = end_date = target_date.date if hasattr(target_date, 'date') else target_date
            logging.info(f"Фильтруем по конкретной дате: {start_date}")
            
        return start_date, end_date

    def _format_days(self, days: List[Dict], date_range: tuple, formatted_schedule: List[str]) -> bool:
        """Форматирует дни расписания"""
        found_lessons = False
        start_date, end_date = date_range
        
        for day in sorted(days, key=lambda x: x["date"]):
            date = datetime.strptime(day["date"], "%Y-%m-%d")
            
            if not self._is_date_in_range(date, start_date, end_date):
                continue
                
            found_lessons = True
            self._format_single_day(day, date, formatted_schedule)
            
        return found_lessons

    def _is_date_in_range(self, date: datetime, start_date: datetime, end_date: datetime) -> bool:
        """Проверяет, входит ли дата в указанный диапазон"""
        if isinstance(start_date, datetime):
            return start_date.date() <= date.date() <= end_date.date()
        return start_date <= date.date() <= end_date

    def _format_single_day(self, day: Dict, date: datetime, formatted_schedule: List[str]) -> None:
        """Форматирует один день расписания"""
        formatted_date = date.strftime('%d\\.%m')
        formatted_schedule.append(f"📅 {self.weekdays[date.weekday()]} {formatted_date}\n")
        
        lessons = day.get("lessons", [])
        if not lessons:
            formatted_schedule.append("Нет занятий\n")
            return
            
        for lesson in sorted(lessons, key=lambda x: int(x.get("number", "0"))):
            formatted_schedule.append(self._format_lesson(lesson))
        formatted_schedule.append("")

    def _format_lesson(self, lesson: Dict) -> str:
        """Форматирует информацию о занятии"""
        number = lesson.get("number", "")
        time_start = lesson.get("timeStart", "").replace(":", "\\:")
        time_end = lesson.get("timeEnd", "").replace(":", "\\:")
        subject = escape_markdown(lesson.get("subject", {}).get("title", ""), version=2)
        
        # Формируем строки занятия
        lines = [
            f"{self._num_to_emoji(number)}🕑 {time_start} \\- {time_end}",
            f"📚 {subject}",
        ]
        
        # Для преподавателей показываем группы
        if self.is_lecturer:
            groups = escape_markdown(lesson.get("groups", {}).get("title", ""), version=2)
            if groups:
                lines.append(f"👥 Группы: {groups}")
        else:
            # Для групп показываем преподавателя
            teacher = escape_markdown(lesson.get("teacher", {}).get("title", ""), version=2)
            if teacher:
                lines.append(f"👩 {teacher}")
        
        # Добавляем аудиторию
        room = lesson.get("classroom", {}).get("title", "").strip()
        room = room.replace('None', '').replace('`', '').strip()
        if room:
            classroom = escape_markdown(room, version=2)
            lines.append(f"🏢 {classroom}")
            
        # Добавляем комментарий
        if "commentary" in lesson:
            lines.append(f"💬 {escape_markdown(lesson['commentary'], version=2)}")
            
        return "\n".join(lines) + "\n"

    def _num_to_emoji(self, num: str) -> str:
        """Конвертирует числовой номер пары в эмодзи"""
        if num.isdigit() and int(num) < len(self.emoji_numbers):
            return self.emoji_numbers[int(num)]
        return "❓"

    def _add_schedule_link(self, formatted_schedule: List[str], schedule_link: str) -> str:
        """Добавляет ссылку на расписание и объединяет все строки"""
        escaped_link = schedule_link.replace(".", "\\.")
        formatted_schedule.append(f"🚀 [Ссылка на расписание]({escaped_link})")
        return "\n".join(formatted_schedule)

# Создаем форматтеры для разных типов расписаний
group_formatter = ScheduleFormatter(is_lecturer=False)
lecturer_formatter = ScheduleFormatter(is_lecturer=True)

def format_schedule(timetable_data: Dict, schedule_link: str, name: str, 
                   target_date: Optional[Union[datetime, 'ScheduleRequest']] = None,
                   is_lecturer: bool = False) -> str:
    """Функция-обертка для обратной совместимости"""
    formatter = lecturer_formatter if is_lecturer else group_formatter
    return formatter.format_schedule(timetable_data, schedule_link, name, target_date)
