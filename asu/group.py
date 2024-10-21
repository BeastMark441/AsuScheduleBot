class Schedule():
    def __init__(self, name: str, faculty_id: int, group_id: int):
        self.name = name
        self.faculty_id = faculty_id
        self.group_id = group_id


    def get_schedule_url(self) -> str:
        return "https://www.asu.ru/timetable/students/{}/{}/".format(self.faculty_id, self.group_id)