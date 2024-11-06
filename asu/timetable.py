from dataclasses import dataclass
from datetime import date

from asu.lecturer import Lecturer
from asu.group import Group

@dataclass
class Room:
    # Address where lecture will be
    address: str
    # Address code. Examples: Н - Комсомольский
    address_code: str
    # Room number where lecture will be
    number: str

@dataclass
class Subject:
    title: str
    # type of subject. Examples: пр.з. ; лек.
    type: str
    # Optional comment. Example: дистанционно-синхронно
    comment: str | None
    # name of groups
    groups: list[Group]
    # name of lecturer
    lecturers: list[Lecturer]
    room: Room

@dataclass
class Lesson:
    # lesson num sorted by time
    number: str
    # time of lesson to start and end. Format: HH:MM
    time_start: str
    time_end: str
    subject: Subject

@dataclass
class TimeTable:
    days: dict[date, list[Lesson]]

