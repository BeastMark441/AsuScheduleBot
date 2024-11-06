from dataclasses import dataclass

@dataclass
class Group:
    """Класс для хранения информации о расписании группы"""
    # Name of the group
    name: str
    faculty_id: str
    group_id: str
    # Some groups may have sub groups to split big groups
    sub_group: str | None = None

    def get_schedule_url(self) -> str:
        """Получить URL для расписания группы"""
        return f"https://www.asu.ru/timetable/students/{self.faculty_id}/{self.group_id}/"

    def __str__(self) -> str:
        return f"Группа {self.name}"