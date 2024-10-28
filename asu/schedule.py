from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Schedule:
    """Класс для хранения информации о расписании группы"""
    name: str
    faculty_id: str
    group_id: str

    def __post_init__(self):
        if not all([self.name, self.faculty_id, self.group_id]):
            raise ValueError("All fields are required")
        
        # Убираем лишние пробелы
        self.name = self.name.strip()
        self.faculty_id = str(self.faculty_id).strip()
        self.group_id = str(self.group_id).strip()

    def get_schedule_url(self, print_mode: bool = True) -> str:
        """Получить URL для расписания группы"""
        return f"https://www.asu.ru/timetable/students/{self.faculty_id}/{self.group_id}/"

    def __str__(self) -> str:
        return f"Группа {self.name}"

@dataclass
class Lecturer:
    """Класс для хранения информации о расписании преподавателя"""
    name: str
    faculty_id: str
    chair_id: str
    lecturer_id: str

    def __post_init__(self):
        if not all([self.name, self.faculty_id, self.chair_id, self.lecturer_id]):
            raise ValueError("All fields are required")
        
        # Убираем лишние пробелы
        self.name = self.name.strip()
        self.faculty_id = str(self.faculty_id).strip()
        self.chair_id = str(self.chair_id).strip()
        self.lecturer_id = str(self.lecturer_id).strip()

    def get_schedule_url(self, print_mode: bool = True) -> str:
        """Получить URL для расписания преподавателя"""
        return f"https://www.asu.ru/timetable/lecturers/{self.faculty_id}/{self.chair_id}/{self.lecturer_id}/"

    def __str__(self) -> str:
        return f"Преподаватель {self.name}"

@dataclass
class ScheduleRequest:
    """Класс для запроса расписания"""
    date: datetime
    is_week_request: bool = False

    def __post_init__(self):
        if not isinstance(self.date, datetime):
            raise ValueError("date must be datetime object")
        if not isinstance(self.is_week_request, bool):
            raise ValueError("is_week_request must be boolean")
