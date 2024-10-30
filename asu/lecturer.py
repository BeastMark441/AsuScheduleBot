from dataclasses import dataclass


@dataclass
class Lecturer:
    """Класс для хранения информации о расписании преподавателя"""
    name: str
    faculty_id: str
    chair_id: str
    lecturer_id: str
    # Position of Lecturer. Examples: асс. преп.
    position: str

    def get_schedule_url(self) -> str:
        """Получить URL для расписания преподавателя"""
        return f"https://www.asu.ru/timetable/lecturers/{self.faculty_id}/{self.chair_id}/{self.lecturer_id}/"

    def __str__(self) -> str:
        return f"Преподаватель {self.name}"
