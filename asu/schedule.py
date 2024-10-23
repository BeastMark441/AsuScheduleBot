class Schedule():
    def __init__(self, name: str, faculty_id: int, group_id: int) -> None:
        self.name = name
        self.faculty_id = faculty_id
        self.group_id = group_id


    def get_schedule_url(self, print_mode: bool = True) -> str:
        r = "https://www.asu.ru/timetable/students/{}/{}/".format(self.faculty_id, self.group_id)

        if print_mode:
            r = r + "?mode=print"

        return r