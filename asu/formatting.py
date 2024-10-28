from datetime import date, datetime, timedelta
from operator import le
from typing import Dict, List, Optional, Union
from frozenlist import FrozenList
from telegram.helpers import escape_markdown
import logging

from asu.timetable import Lesson, TimeTable

from utils.sub_format import get_sub
from utils.daterange import DateRange

EMOJI_NUMBERS: FrozenList[str] = FrozenList(["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"])
USER_FRIENDLY_WEEKDAYS: FrozenList[str] = FrozenList(["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"])

class ScheduleFormatter:
    """Класс для форматирования расписания"""
    
    def __init__(self, is_lecturer: bool = False):
        self.is_lecturer = is_lecturer

    def format_schedule(self, timetable: TimeTable, schedule_link: str, name: str,
                       date_range: DateRange) -> str:
        """Форматирует расписание в текстовый вид"""
        logging.info("Форматирование расписания для %s %s", 'преподавателя' if self.is_lecturer else 'группы', name)
        
        # Формируем заголовок
        header_emoji: str = "👩‍🏫" if self.is_lecturer else "📚"
        header_text: str = "преподавателя" if self.is_lecturer else "группы"
        formatted_schedule: list[str] = [f"{header_emoji} Расписание {header_text}: {escape_markdown(name, version=2)}\n"]
        
        if not timetable.days:
            formatted_schedule.append("На указанный период занятий не найдено\\.")
            return self._add_schedule_link(formatted_schedule, schedule_link)
            
        # Форматируем дни
        found_lessons = self._format_days(timetable, date_range, formatted_schedule)
        
        if not found_lessons:
            formatted_schedule.append("На указанный период занятий не найдено\\.")
            
        return self._add_schedule_link(formatted_schedule, schedule_link)

    def _format_days(self, timetable: TimeTable, date_range: DateRange, formatted_schedule: list[str]) -> bool:
        """Форматирует дни расписания"""
        found_lessons = False

        for date, lessons in sorted(timetable.days.items(), key=lambda item: item[0]):
            if not date_range.is_date_in_range(date):
                continue
                
            found_lessons = True
            self._format_single_day(lessons, date, formatted_schedule)
            
        return found_lessons

    def _is_date_in_range(self, date: datetime, start_date: datetime, end_date: datetime) -> bool:
        """Проверяет, входит ли дата в указанный диапазон"""
        if isinstance(start_date, datetime):
            return start_date.date() <= date.date() <= end_date.date()
        return start_date <= date.date() <= end_date

    def _format_single_day(self, lessons: list[Lesson], date: date, formatted_schedule: list[str]) -> None:
        """Форматирует один день расписания"""
        formatted_date = date.strftime('%d.%m')
        formatted_schedule.append(f"📅 {USER_FRIENDLY_WEEKDAYS[date.weekday()]} {escape_markdown(formatted_date, version=2)}\n")
        
        if not lessons:
            formatted_schedule.append("Нет занятий\n")
            return
            
        for lesson in lessons:
            formatted_schedule.append(self._format_lesson(lesson))
        formatted_schedule.append("")

    def _format_lesson(self, lesson: Lesson) -> str:
        """Форматирует информацию о занятии"""

        lesson_subgroups: set[str] = set()
        for group in lesson.subject.groups:
            if group.sub_group:
                lesson_subgroups.update(get_sub(group.sub_group))

        lesson_subgroups_str = ''.join(lesson_subgroups)
        subject_title = escape_markdown(f"{lesson.subject.type} {lesson.subject.title}", version=2)

        # Формируем строки занятия
        lines = [
            f"{self._num_to_emoji(lesson.number)}🕑 {escape_markdown(lesson.time_start, version=2)} \\- {escape_markdown(lesson.time_end, version=2)}",
            f"📚 {lesson_subgroups_str}{subject_title}",
        ]
        
        # Для преподавателей показываем группы
        if self.is_lecturer:
            groups: set[str] = set()

            for group in lesson.subject.groups:
                groups.update(group.name)

            if not groups:
                groups.update("❓")

            lines.append(f"👥 Группы: {escape_markdown(' '.join(groups), version=2)}")
        else:
            lecturers: set[str] = set()

            for lecturer in lesson.subject.lecturers:
                lecturers.update(lecturer.name)

            if not lecturer:
                lecturer = "❓"
            
            lines.append(f"👩 {escape_markdown(' '.join(lecturers), version=2)}")

        # Добавляем аудиторию
        room = escape_markdown(f"{lesson.subject.room.number} {lesson.subject.room.address_code}", version=2)
        lines.append(f"🏢 {room}")

        # Добавляем комментарий
        if lesson.subject.comment:
            lines.append(f"💬 {escape_markdown(lesson.subject.comment, version=2)}")
            
        return "\n".join(lines) + "\n"

    @staticmethod
    def _num_to_emoji(num: str) -> str:
        """Конвертирует числовой номер пары в эмодзи"""
        if num.isdigit() and int(num) < len(EMOJI_NUMBERS):
            return EMOJI_NUMBERS[int(num)]
        return "❓"

    @staticmethod
    def _add_schedule_link(formatted_schedule: list[str], schedule_link: str) -> str:
        """Добавляет ссылку на расписание и объединяет все строки"""
        formatted_schedule.append(f"🚀 [Ссылка на расписание]({escape_markdown(schedule_link)})")
        return "\n".join(formatted_schedule)

# Создаем форматтеры для разных типов расписаний
group_formatter = ScheduleFormatter(is_lecturer=False)
lecturer_formatter = ScheduleFormatter(is_lecturer=True)

def format_schedule(timetable_data: TimeTable, schedule_link: str, name: str, 
                   target_date: DateRange, is_lecturer: bool) -> str:
    """Функция-обертка для обратной совместимости"""
    formatter = lecturer_formatter if is_lecturer else group_formatter
    return formatter.format_schedule(timetable_data, schedule_link, name, target_date)
