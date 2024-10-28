import os
import httpx
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, TypeVar, Any
from functools import lru_cache
from .schedule import Schedule, Lecturer, ScheduleRequest  # Добавляем импорт ScheduleRequest

# Типизация для улучшения читаемости
ScheduleType = TypeVar('ScheduleType', Schedule, Lecturer)
DateType = Union[datetime, 'ScheduleRequest']

class APIClient:
    def __init__(self, token: str):
        if not token:
            raise ValueError("API token is required")
        self.token = token
        self.client = httpx.AsyncClient(timeout=30.0)
        self.base_url = "https://www.asu.ru/timetable"
        
    async def close(self):
        await self.client.aclose()
        
    def _build_url(self, endpoint: str) -> str:
        return f"{self.base_url}/{endpoint}"
    
    def _build_params(self, extra_params: Dict[str, str] = None) -> Dict[str, str]:
        params = {'file': 'list.json', 'api_token': self.token}
        if extra_params:
            params.update(extra_params)
        return params
        
    async def _make_request(self, url: str, params: Dict[str, str]) -> Dict:
        try:
            await asyncio.sleep(2)  # Rate limiting
            response = await self.client.get(url, params=params, follow_redirects=True)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"API request failed: {str(e)}")
            raise

    async def search_group(self, query: str) -> Optional[Schedule]:
        if not query.strip():
            return None
            
        url = self._build_url("search/students/")
        params = self._build_params({'query': convert_to_russian(query.strip())})
        
        try:
            data = await self._make_request(url, params)
            groups = data.get("groups", {}).get("records", [])
            
            if not groups:
                return None
                
            record = groups[0]
            faculty_id = record["path"].split("/")[0]
            return Schedule(record["groupCode"], faculty_id, record["groupId"])
        except Exception as e:
            logging.error(f"Failed to search group: {str(e)}")
            return None

    async def search_lecturer(self, query: str) -> Optional[Lecturer]:
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
                lecturer_id=path_parts[2]
            )
        except Exception as e:
            logging.error(f"Failed to search lecturer: {str(e)}")
            return None

    async def get_schedule(self, schedule: ScheduleType, target_date: Optional[DateType] = None) -> Dict:
        if not schedule:
            return {"days": []}
            
        url = schedule.get_schedule_url()
        params = self._build_params()
        
        if target_date:
            params['date'] = self._format_date_param(target_date)
            
        try:
            data = await self._make_request(url, params)
            logging.debug(f"Получены данные расписания: {data}")
            
            is_lecturer = isinstance(schedule, Lecturer)
            logging.debug(f"Тип расписания: {'преподаватель' if is_lecturer else 'группа'}")
            
            schedule_data = data.get("schedule", {})
            records = schedule_data.get("records", [])
            logging.info(f"Найдено {len(records)} записей в расписании")
            logging.debug(f"Записи расписания: {records}")
            
            if not records:
                logging.warning("Расписание пустое")
                return {"days": []}
                
            processed_data = self._process_schedule_data(records, target_date, is_lecturer)
            logging.info(f"Обработано дней: {len(processed_data['days'])}")
            logging.debug(f"Обработанные данные: {processed_data}")
            return processed_data
        except Exception as e:
            logging.error(f"Failed to get schedule: {str(e)}")
            return {"days": []}

    @staticmethod
    def _format_date_param(target_date: DateType) -> str:
        if hasattr(target_date, 'is_week_request') and target_date.is_week_request:
            start_date = target_date.date - timedelta(days=target_date.date.weekday())
            end_date = start_date + timedelta(days=6)
            return f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"
        else:
            target_day = target_date.date if hasattr(target_date, 'date') else target_date
            return target_day.strftime('%Y%m%d')

    @staticmethod
    def _process_schedule_data(records: List[Dict], target_date: Optional[DateType], is_lecturer: bool = False) -> Dict:
        days_dict = {}
        
        for record in records:
            date = record.get("lessonDate")
            if not date:
                continue
                
            formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
            
            if target_date and not hasattr(target_date, 'is_week_request'):
                target_day = target_date.date if hasattr(target_date, 'date') else target_date
                if date != target_day.strftime('%Y%m%d'):
                    continue

            if formatted_date not in days_dict:
                days_dict[formatted_date] = []

            # Убираем проверку lecturerId, так как она некорректна
            lesson = APIClient._format_lesson(record, is_lecturer)
            days_dict[formatted_date].append(lesson)

        # Сортируем дни и занятия
        days = [
            {"date": date, "lessons": sorted(lessons, key=lambda x: int(x.get("number", "0")))}
            for date, lessons in sorted(days_dict.items())
            if lessons  # Добавляем только дни с занятиями
        ]
        
        logging.debug(f"Обработанные дни: {days}")
        return {"days": days}

    @staticmethod
    def _format_lesson(record: Dict, is_lecturer: bool = False) -> Dict:
        lesson = {
            "number": record.get("lessonNum", ""),
            "timeStart": record.get("lessonTimeStart", ""),
            "timeEnd": record.get("lessonTimeEnd", ""),
            "subject": {"title": record.get("lessonSubject", {}).get("subjectTitle", "")},
        }

        # Для преподавателей добавляем группы вместо преподавателя
        if is_lecturer:
            groups = record.get("lessonGroups", [])
            group_names = [g.get("lessonGroup", {}).get("groupCode", "") for g in groups if g.get("lessonGroup")]
            lesson["groups"] = {"title": ", ".join(filter(None, group_names))}
        else:
            lecturer = record.get("lessonLecturers", [{}])[0]
            lesson["teacher"] = {"title": lecturer.get("lecturerName", "")}

        # Добавляем информацию об аудитории
        room_title = record.get('lessonRoom', {}).get('roomTitle', '')
        building_code = record.get('lessonBuilding', {}).get('buildingCode', '')
        if room_title or building_code:
            classroom = f"{room_title} {building_code}".strip()
            if classroom:  # Добавляем только если не пустая строка
                lesson["classroom"] = {"title": classroom}

        # Добавляем комментарий, если есть
        if commentary := record.get("lessonCommentary"):
            lesson["commentary"] = commentary

        return lesson

@lru_cache(maxsize=1000)
def convert_to_russian(text: str) -> str:
    """Кэшированная функция конвертации латиницы в кириллицу"""
    conversion_map = {
        'a': 'а', 'b': 'в', 'c': 'с', 'd': 'д', 'e': 'е', 'f': 'ф',
        'g': 'г', 'h': 'х', 'i': 'и', 'j': 'й', 'k': 'к', 'l': 'л',
        'm': 'м', 'n': 'н', 'o': 'о', 'p': 'р', 'q': 'к', 'r': 'р',
        's': 'с', 't': 'т', 'u': 'у', 'v': 'в', 'w': 'в', 'x': 'х',
        'y': 'у', 'z': 'з'
    }
    return ''.join(conversion_map.get(char.lower(), char) for char in text)

# Создаем глобальный экземпляр клиента
api_client = APIClient(os.getenv('ASU', ''))

# Экспортируем функции для обратной совместимости
async def find_schedule_url(group_name: str) -> Optional[Schedule]:
    return await api_client.search_group(group_name)

async def find_lecturer_schedule(lecturer_name: str) -> Optional[Lecturer]:
    return await api_client.search_lecturer(lecturer_name)

async def get_timetable(schedule: ScheduleType, target_date: Optional[DateType] = None) -> Dict:
    return await api_client.get_schedule(schedule, target_date)
