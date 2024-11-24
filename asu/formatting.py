from datetime import date
from html import escape
import logging

from asu.timetable import Lesson, TimeTable

from utils.daterange import DateRange

EMOJI_NUMBERS: list[str] = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
USER_FRIENDLY_WEEKDAYS: list[str] = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

class ScheduleFormatter:
    """Класс для форматирования расписания"""
    
    def __init__(self, is_lecturer: bool = False):
        self.is_lecturer: bool = is_lecturer

    def format_schedule(self, timetable: TimeTable, schedule_link: str, name: str,
                       date_range: DateRange) -> str:
        """Форматирует расписание в текстовый вид"""
        logging.info("Форматирование расписания для %s %s", 'преподавателя' if self.is_lecturer else 'группы', name)
        
        # Формируем заголовок
        header_emoji: str = "👩‍🏫" if self.is_lecturer else "📚"
        header_text: str = "преподавателя" if self.is_lecturer else "группы"
        formatted_schedule: list[str] = [f"{header_emoji} Расписание {header_text}: {escape(name)}\n"]
        
        if not timetable.days:
            formatted_schedule.append("На указанный период занятий не найдено.")
            return self._add_schedule_link(formatted_schedule, schedule_link)
            
        # Форматируем дни
        found_lessons = self._format_days(timetable, date_range, formatted_schedule)
        
        if not found_lessons:
            formatted_schedule.append("На указанный период занятий не найдено.")
            
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

    def _format_single_day(self, lessons: list[Lesson], date: date, formatted_schedule: list[str]) -> None:
        """Форматирует один день расписания"""
        formatted_date = date.strftime('%d.%m')
        formatted_schedule.append(f"📅 {USER_FRIENDLY_WEEKDAYS[date.weekday()]} {escape(formatted_date)}\n")
        
        if not lessons:
            formatted_schedule.append("Нет занятий\n")
            return
            
        for lesson in lessons:
            formatted_schedule.append(self._format_lesson(lesson))
        formatted_schedule.append("")

    def _format_lesson(self, lesson: Lesson) -> str:
        """Форматирует информацию о занятии в табличном стиле"""
        
        # Подгруппы
        lesson_subgroups = lesson.subject.sub_groups or []
        subgroups = ''.join([f"<i>{escape(group)}</i> " for group in lesson_subgroups])
        
        # Время
        time_block = f"{self._num_to_emoji(lesson.number)} {escape(lesson.time_start)}-{escape(lesson.time_end)}"
        
        # Предмет
        subject_block = f"📚 {subgroups}{escape(lesson.subject.type)} {escape(lesson.subject.title)}"
        
        # Преподаватели или группы
        if self.is_lecturer:
            groups = set([group.name for group in lesson.subject.groups]) or {"❓"}
            people_block = f"👥 {escape(' '.join(groups))}"
        else:
            lecturers = set([f"преп. {lecturer.name}" for lecturer in lesson.subject.lecturers]) or {"❓"}
            people_block = f"👩 {escape(' '.join(lecturers))}"
        
        # Аудитория
        room_block = f"🏢 {escape(f'{lesson.subject.room.number} {lesson.subject.room.address_code}')}"
        
        # Формируем табличный вывод
        formatted = (
            f"┌─ {time_block}\n"
            f"├─ {subject_block}\n"
            f"├─ {people_block}\n"
            f"└─ {room_block}\n"
        )
        
        # Добавляем комментарий если есть
        if lesson.subject.comment:
            formatted = formatted[:-1] + f"\n└─ 💬 {escape(lesson.subject.comment)}\n"
        
        return formatted

    @staticmethod
    def _num_to_emoji(num: str) -> str:
        """Конвертирует числовой номер пары в эмодзи"""
        if num.isdigit() and int(num) < len(EMOJI_NUMBERS):
            return EMOJI_NUMBERS[int(num)]
        return "❓"

    @staticmethod
    def _add_schedule_link(formatted_schedule: list[str], schedule_link: str) -> str:
        """Добавляет ссылку на расписание и объединяет все строки"""
        formatted_schedule.append(f"🚀 <a href=\"{escape(schedule_link)}\">Ссылка на расписание</a>")
        return "\n".join(formatted_schedule)

# Создаем форматтеры для разных типов расписаний
group_formatter = ScheduleFormatter(is_lecturer=False)
lecturer_formatter = ScheduleFormatter(is_lecturer=True)

def format_schedule(timetable_data: TimeTable, schedule_link: str, name: str, 
                   target_date: DateRange, is_lecturer: bool) -> str:
    """Функция-обертка для обратной совместимости"""
    formatter = lecturer_formatter if is_lecturer else group_formatter
    return formatter.format_schedule(timetable_data, schedule_link, name, target_date)
