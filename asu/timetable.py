from dataclasses import dataclass, asdict
from datetime import date
from typing import Any
import json

from asu.group import Group
from asu.lecturer import Lecturer

@dataclass
class Room:
    address: str
    address_code: str
    number: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Room':
        return cls(**data)

@dataclass
class Subject:
    title: str
    type: str
    comment: str | None
    groups: list[Group]
    lecturers: list[Lecturer]
    room: Room

    def to_dict(self) -> dict[str, Any]:
        return {
            'title': self.title,
            'type': self.type,
            'comment': self.comment,
            'groups': [asdict(g) for g in self.groups],
            'lecturers': [asdict(l) for l in self.lecturers],
            'room': self.room.to_dict()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Subject':
        data['groups'] = [Group(**g) for g in data['groups']]
        data['lecturers'] = [Lecturer(**l) for l in data['lecturers']]
        data['room'] = Room.from_dict(data['room'])
        return cls(**data)

@dataclass
class Lesson:
    number: str
    time_start: str
    time_end: str
    subject: Subject

    def to_dict(self) -> dict[str, Any]:
        return {
            'number': self.number,
            'time_start': self.time_start,
            'time_end': self.time_end,
            'subject': self.subject.to_dict()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Lesson':
        data['subject'] = Subject.from_dict(data['subject'])
        return cls(**data)

@dataclass
class TimeTable:
    days: dict[date, list[Lesson]]

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        return {
            date_.isoformat(): [lesson.to_dict() for lesson in lessons]
            for date_, lessons in self.days.items()
        }

    @classmethod
    def from_dict(cls, data: dict[str, list[dict[str, Any]]]) -> 'TimeTable':
        return cls({
            date.fromisoformat(date_str): [Lesson.from_dict(l) for l in lessons]
            for date_str, lessons in data.items()
        })

