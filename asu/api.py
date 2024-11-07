import os
from typing import Any
import httpx
import asyncio
import logging
from datetime import date, datetime

from .timetable import Lesson, Room, Subject, TimeTable
from .group import Group
from .lecturer import Lecturer
from utils.daterange import DateRange
from utils.latin_to_ru import convert_to_russian

ScheduleType = Group | Lecturer

logger: logging.Logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self, token: str) -> None:
        if not token:
            raise ValueError("API token is required")
        self.token: str = token
        self.client: httpx.AsyncClient = httpx.AsyncClient(timeout=30.0)
        self.base_url: str = "https://www.asu.ru/timetable"

        # lookup dict to get faculty id from code name
        # Example: СПО - 15
        self.faculties: dict[str, str] = dict()
        
    async def create_list_of_faculty_if_empty(self) -> None:
        if self.faculties:
            return

        faculties = await self._make_request(self._build_url("students"), self._build_params())
        records: dict[Any, Any] = faculties.get("faculties", {}).get("records", {})

        for record in records:
            code = record.get("facultyCode")
            id = record.get("facultyId")

            if code and id:
                self.faculties[code] = id

        if len(self.faculties) == 0:
            raise ValueError("Failed to get faculties.")
    
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
        if not query.strip():
            return None
            
        url = self._build_url("search/students/")
        params = self._build_params({'query': query.strip()})
        
        try:
            data = await self._make_request(url, params)
            groups = data.get("groups", {}).get("records", [])
            
            if not groups:
                return None
                
            record = groups[0]
            faculty_id = record["path"].split("/")[0]
            return Group(record["groupCode"], faculty_id, record["groupId"])
        except Exception as e:
            logging.error(f"Failed to search group: {str(e)}")
            return None

    async def search_lecturer(self, query: str) -> Lecturer | None:
        if not query.strip():
            return None
            
        url = self._build_url("search/lecturers/")
        params = self._build_params({'query': convert_to_russian(query.strip())})
        
        try:
            data = await self._make_request(url, params)
            lecturers = data.get("lecturers", {}).get("records", [])
            
            if not lecturers:
                return None
                
            record = lecturers[0]
            path_parts = record["path"].rstrip('/').split('/')
            
            if len(path_parts) < 3:
                return None
                
            return Lecturer(
                name=record["lecturerName"],
                faculty_id=path_parts[0],
                chair_id=path_parts[1],
                lecturer_id=path_parts[2],
                position="" # FIXME
            )
        except Exception as e:
            logger.error(f"Failed to search lecturer: {str(e)}")
            return None

    async def get_schedule(self, schedule: ScheduleType, target_date: DateRange) -> TimeTable:
        # initialize dict lookup
        await self.create_list_of_faculty_if_empty()
        
        url: str = schedule.get_schedule_url()
        params: dict[str, str] = self._build_params()
        
        params['date'] = self._format_date_param(target_date)
            
        try:
            data = await self._make_request(url, params)

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Получены данные расписания: {data}")
            
            is_lecturer = isinstance(schedule, Lecturer)
            logger.debug("Тип расписания: %s", 'преподаватель' if is_lecturer else 'группа')
            
            schedule_data: dict[Any, Any] = data.get("schedule", {})
            records: list[dict[Any, Any]] = schedule_data.get("records", [])
            logger.info("Найдено %d записей в расписании", len(records))

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Записи расписания: {}".format(records))
            
            if not records:
                logger.warning("Расписание пустое")
                return TimeTable({})
                
            time_table = self._process_schedule_data(records, target_date)
            logger.info("Обработано дней: %d", len(time_table.days))

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Обработанные данные: {}".format(time_table))

            return time_table
        except Exception as e:
            logging.error(f"Failed to get schedule: {str(e)}")
            return TimeTable({})

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

        group_record: dict[Any, Any]
        for group_record in record.get("lessonGroups", []):
            lesson_group_record = group_record.get("lessonGroup", {})

            group_name = lesson_group_record.get("groupCode") or ""
            faculty_code = lesson_group_record.get("groupFacultyCode") or ""
            group_id = lesson_group_record.get("groupId") or ""

            faculty_id = self.faculties.get(faculty_code) or ""
            sub_group = (group_record.get("lessonSubGroup") or "").strip()

            group = Group(group_name, faculty_id, group_id, sub_group)
            groups.append(group)

        lecturers: list[Lecturer] = []

        for lecturer_record in record.get("lessonLecturers", []):
            name = lecturer_record.get("lecturerName", "")
            chair_id = lecturer_record.get("lecturerIdChair", "")
            lecturer_id = lecturer_record.get("lecturerId", "")
            lecturer_faculty_code = lecturer_record.get("lecturerChairFacultyCode", "")
            lecturer_position = lecturer_record.get("lecturerPosition", "")

            faculty_id = self.faculties.get(lecturer_faculty_code, "")

            lecturer = Lecturer(name, faculty_id, chair_id, lecturer_id, lecturer_position)
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

# Создаем глобальный экземпляр клиента
api_client = APIClient(os.getenv('ASU', ''))

# Экспортируем функции для обратной совместимости
async def find_schedule_url(group_name: str) -> Group | None:
    return await api_client.search_group(group_name)

async def find_lecturer_schedule(lecturer_name: str) -> Lecturer | None:
    return await api_client.search_lecturer(lecturer_name)

async def get_timetable(schedule: ScheduleType, target_date: DateRange) -> TimeTable:
    return await api_client.get_schedule(schedule, target_date)
