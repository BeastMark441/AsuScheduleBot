import asyncio
from datetime import date, datetime
import logging
from typing import Any

import httpx
from sqlalchemy import select

from database.db import create_session
from database.models import Faculty, Group, Lecturer
import database.models as models
from settings import Settings
from utils.daterange import DateRange

from .timetable import Lesson, Room, Subject, TimeTable

ScheduleType = Group | Lecturer

_logger: logging.Logger = logging.getLogger(__name__)
_settings: Settings = Settings()

class APIClient:
    def __init__(self, token: str) -> None:
        if not token:
            raise ValueError("API token is required")
        
        self.token: str = token
        self.client: httpx.AsyncClient = httpx.AsyncClient()
        self.base_url: str = "https://www.asu.ru/timetable"
        self.faculties: dict[str, int] = {}
        
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.load_faculties())

    async def load_faculties(self) -> None:
        stmt = select(Faculty)
        
        async for session in create_session():
            async with session.begin():
                result = await session.execute(stmt)
                
                for faculty in result.scalars():
                    self.faculties[faculty.faculty_code] = faculty.faculty_id
                    
        if not self.faculties:
            raise ValueError("Failed to load data. Is database correctly installed?")
    
    def _build_url(self, endpoint: str) -> str:
        return f"{self.base_url}/{endpoint}"
    
    def _build_params(self, extra_params: dict[str, str] | None = None) -> dict[str, str]:
        params: dict[str, str] = {'file': 'list.json', 'api_token': self.token}
        if extra_params:
            params.update(extra_params)
        return params
    
    async def _make_request(self, url: str, params: dict[str, str]) -> dict[Any, Any]:
        try:
            await asyncio.sleep(2)  # Rate limiting
            response = await self.client.get(url, params=params, follow_redirects=True)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"API request failed: {str(e)}")
            raise

    async def search_group(self, query: str) -> Group | None:
        # Limit to 50 chars
        query = query.strip()[:50]
        
        if not query:
            return None
        
        # Check in database first
        stmt = select(models.Group).where(models.Group.name.like("%{}%".format(query)))
        async for session in create_session():
            async with session.begin():
                result = await session.execute(stmt)
                group = result.scalar()
                
                if group:
                    return group
                
        # Sad, not in the database, query the API then
        url = self._build_url("search/students/")
        params = self._build_params({'query': query})
        
        data = await self._make_request(url, params)
        groups = data.get("groups", {}).get("records", [])
        
        if not groups:
            return None
            
        record = groups[0]
        faculty_id = record["path"].split("/")[0]
        group_code = record["groupCode"] # or group name
        group_id = record["groupId"]
        
        group = models.Group(
                    group_id=int(group_id),
                    faculty_id=int(faculty_id),
                    name=group_code
                )
        
        # cache the result to database
        async for session in create_session():
            async with session.begin():
                session.add(group)
                
                await session.commit()
        
        return group

    async def search_lecturer(self, query: str) -> Lecturer | None:
        # Limit to 50 chars
        query = query.strip()[:50]
        
        if not query:
            return None
        
        # Check in database first
        stmt = select(models.Lecturer).where(models.Lecturer.name.like("%{}%".format(query)))
        async for session in create_session():
            async with session.begin():                
                result = await session.execute(stmt)
                lecturer = result.scalar()
                
                if lecturer:
                    return lecturer
           
        # Sad, not in the database, query the API then
        url = self._build_url("search/lecturers/")
        params = self._build_params({'query': query})
        
        data = await self._make_request(url, params)
        lecturers = data.get("lecturers", {}).get("records", [])
        
        if not lecturers:
            return None
            
        record = lecturers[0]
        lecturer_faculty_id = record["path"].split("/")[0] # FACULTY_ID/CHAIR_ID/LECTURER_ID
        lecturer_id = record["lecturerId"]
        lecturer_name = record["lecturerName"]
        lecturer_position = record["lecturerPosition"]
        lecturer_id_chair = record["lecturerIdChair"]
        
        # cache the result to database
        async for session in create_session():
            async with session.begin():
                session.add(models.Lecturer(
                    lecturer_id=int(lecturer_id),
                    faculty_id=int(lecturer_faculty_id),
                    chair_id=int(lecturer_id_chair),
                    name=lecturer_name,
                    position=lecturer_position,
                ))
                
                await session.commit()
            
        return Lecturer(
            name=lecturer_name,
            faculty_id=lecturer_faculty_id,
            chair_id=lecturer_id_chair,
            lecturer_id=lecturer_id_chair,
            position=lecturer_position
        )

    async def get_schedule(self, schedule: ScheduleType, target_date: DateRange) -> TimeTable:
        # todo: add caching
        
        url: str = schedule.schedule_url
        params: dict[str, str] = self._build_params()
        
        params['date'] = self._format_date_param(target_date)
            
        data = await self._make_request(url, params)

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(f"Получены данные расписания: {data}")
        
        is_lecturer = isinstance(schedule, Lecturer)
        _logger.debug("Тип расписания: %s", 'преподаватель' if is_lecturer else 'группа')
        
        schedule_data: dict[Any, Any] = data.get("schedule", {})
        records: list[dict[Any, Any]] = schedule_data.get("records", [])
        _logger.info("Найдено %d записей в расписании", len(records))

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug("Записи расписания: {}".format(records))
        
        if not records:
            _logger.warning("Расписание пустое")
            return TimeTable({})
            
        time_table = self._process_schedule_data(records, target_date)
        _logger.info("Обработано дней: %d", len(time_table.days))

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug("Обработанные данные: {}".format(time_table))

        return time_table

    @staticmethod
    def _format_date_param(target_date: DateRange) -> str:
        if target_date.end_date is None:
            return target_date.start_date.strftime('%Y%m%d')

        return target_date.start_date.strftime('%Y%m%d') + "-" + target_date.end_date.strftime('%Y%m%d')

    def _process_schedule_data(self, records: list[dict[Any, Any]], target_date: DateRange) -> TimeTable:
        days_dict: dict[date, list[Lesson]] = {}
        
        for record in records:
            lesson_date: str = record.get("lessonDate") or ""
            if not lesson_date:
                continue
            
            # format YYYYMMDD
            formatted_date: date = datetime.strptime(lesson_date, "%Y%m%d").date()
            
            if not target_date.is_date_in_range(formatted_date):
                continue

            if formatted_date not in days_dict:
                days_dict[formatted_date] = []

            lesson = self._format_lesson(record)
            days_dict[formatted_date].append(lesson)

        # Сортируем дни и занятия
        
        for d, day in days_dict.items():
            days_dict[d] = sorted(day, key=lambda l: int(l.number))

        return TimeTable(days_dict)
    
    def _get_subject(self, record: dict[Any, Any]) -> Subject:
        groups: list[Group] = []
        sub_groups: list[str] = []

        group_record: dict[Any, Any]
        for group_record in record.get("lessonGroups", []):
            lesson_group_record = group_record.get("lessonGroup", {})

            group_name = lesson_group_record.get("groupCode") or ""
            faculty_code = lesson_group_record.get("groupFacultyCode") or ""
            group_id = lesson_group_record.get("groupId") or ""

            faculty_id = self.faculties.get(faculty_code) or ""
            sub_group = (group_record.get("lessonSubGroup") or "").strip()

            group = Group(group_id=int(group_id), faculty_id=int(faculty_id),
                          name=group_name)
            groups.append(group)
            
            if sub_group:
                sub_groups.append(sub_group)

        lecturers: list[Lecturer] = []

        for lecturer_record in record.get("lessonLecturers", []):
            name = lecturer_record.get("lecturerName", "")
            chair_id = lecturer_record.get("lecturerIdChair", "")
            lecturer_id = lecturer_record.get("lecturerId", "")
            lecturer_faculty_code = lecturer_record.get("lecturerChairFacultyCode", "")
            lecturer_position = lecturer_record.get("lecturerPosition", "")

            faculty_id = self.faculties.get(lecturer_faculty_code, "")

            lecturer = Lecturer(lecturer_id=int(lecturer_id),
                                faculty_id=int(faculty_id),
                                chair_id=int(chair_id),
                                name=name,
                                position=lecturer_position)
            lecturers.append(lecturer)

        building = record.get("lessonBuilding", {})
        address = building.get("buildingAddress", "")
        address_code = building.get("buildingCode", "")

        if isinstance(address_code, str) and address_code == '`':
            # address code can only be that symbol, if it was then clean the result
            address_code = ""

        lesson_room = record.get("lessonRoom", {}).get("roomTitle", "") or ""

        room = Room(address, address_code, lesson_room)

        subject_title = record.get("lessonSubject", {}).get("subjectTitle", "")
        subject_type = (record.get("lessonSubjectType") or "").strip()
        subject_comment = (record.get("lessonCommentary") or "").strip()

        return Subject(title=subject_title, type=subject_type, comment=subject_comment, groups=groups, lecturers=lecturers, room=room)

    def _format_lesson(self, record: dict[Any, Any]) -> Lesson:
        number = record.get("lessonNum", "")
        time_start = record.get("lessonTimeStart", "")
        time_end = record.get("lessonTimeEnd", "")

        subject = self._get_subject(record)
        lesson = Lesson(number, time_start, time_end, subject)
        
        return lesson

client: APIClient = APIClient(token=_settings.ASU_TOKEN)