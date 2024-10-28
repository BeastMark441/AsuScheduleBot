import httpx
import asyncio
import re
import os
import logging
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any
from dotenv import load_dotenv

from .schedule import Schedule

# Загрузка переменных окружения
load_dotenv()

TOKEN = os.getenv('ASU')
if not TOKEN:
    raise ValueError("Токен ASU не найден в переменных окружения")

client = httpx.AsyncClient()

def convert_to_russian(text: str) -> str:
    conversion_map = {
        'a': 'а', 'b': 'в', 'c': 'с', 'd': 'д', 'e': 'е', 'f': 'ф',
        'g': 'г', 'h': 'х', 'i': 'и', 'j': 'й', 'k': 'к', 'l': 'л',
        'm': 'м', 'n': 'н', 'o': 'о', 'p': 'р', 'q': 'к', 'r': 'р',
        's': 'с', 't': 'т', 'u': 'у', 'v': 'в', 'w': 'в', 'x': 'х',
        'y': 'у', 'z': 'з'
    }
    return ''.join(conversion_map.get(char.lower(), char) for char in text)

async def find_schedule_url(group_name: str) -> Optional[Schedule]:
    converted_group_name = convert_to_russian(group_name)
    search_url = f"https://www.asu.ru/timetable/search/students/?query={converted_group_name}&file=list.json&api_token={TOKEN}"
    logging.info(f"Поиск расписания для группы: {group_name} (конвертировано: {converted_group_name})")
    
    try:
        response = await client.get(search_url)
        response.raise_for_status()
        
        # Логируем сырой ответ
        raw_response = response.text
        logging.debug(f"Сырой ответ поиска: {raw_response}")
        
        try:
            json = response.json()
        except ValueError as e:
            logging.error(f"Не удалось распарсить JSON при поиске. Ответ сервера: {raw_response}")
            raise
            
        logging.info(f"Структура результата поиска: {list(json.keys()) if isinstance(json, dict) else 'не словарь'}")

        if "error" in json or "message" in json:
            error_msg = json.get("error") or json.get("message")
            logging.warning(f"API вернул ошибку при поиске: {error_msg}")
            return None

        groups = json.get("groups", {})
        if not groups or int(groups.get("rows", 0)) == 0:
            logging.warning("Группы не найдены")
            return None

        records = groups.get("records", [])
        if not records:
            logging.warning("Записи не найдены")
            return None

        record = records[0]
        logging.info(f"Найдена запись группы: {record}")
        
        faculty_id = record["path"].split("/")[0]
        schedule = Schedule(record["groupCode"], faculty_id, record["groupId"])
        logging.info(f"Создан объект расписания: {schedule.name} (faculty_id: {faculty_id}, group_id: {schedule.group_id})")
        return schedule
    except httpx.HTTPError as e:
        logging.error(f"Ошибка HTTP при поиске расписания: {e}")
        return None
    except ValueError as e:
        logging.error(f"Ошибка при разборе JSON: {e}")
        return None
    except Exception as e:
        logging.error(f"Неожиданная ошибка при поиске расписания: {str(e)}")
        return None

async def get_timetable(schedule: Schedule, target_date: Optional[Union[datetime, 'ScheduleRequest']] = None) -> Dict:
    base_url = schedule.get_schedule_url()
    params = {}
    
    if target_date:
        if isinstance(target_date, datetime):
            date_param = target_date.strftime('%Y%m%d')
            logging.info(f"Запрашиваем расписание на дату: {target_date.strftime('%Y-%m-%d')}")
        else:  # ScheduleRequest
            if target_date.is_week_request:
                start_of_week = target_date.date - timedelta(days=target_date.date.weekday())
                end_of_week = start_of_week + timedelta(days=6)
                date_param = f"{start_of_week.strftime('%Y%m%d')}-{end_of_week.strftime('%Y%m%d')}"
                logging.info(f"Запрашиваем расписание на неделю: {start_of_week.strftime('%Y-%m-%d')} - {end_of_week.strftime('%Y-%m-%d')}")
            else:
                # Для запроса на конкретный день используем диапазон в один день
                date_param = target_date.date.strftime('%Y%m%d')
                logging.info(f"Запрашиваем расписание на дату: {target_date.date.strftime('%Y-%m-%d')}")
            
        params['date'] = date_param
    
    params['file'] = 'list.json'
    params['api_token'] = TOKEN
    
    param_strings = [f"{k}={v}" for k, v in params.items()]
    url = f"{base_url}?{'&'.join(param_strings)}"
    
    logging.info(f"Запрашиваем расписание по URL: {url}")

    try:
        await asyncio.sleep(2)
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        
        data = response.json()
        logging.debug(f"Получен ответ от API: {data}")  # Добавляем полный вывод ответа для отладки
        
        if isinstance(data, dict):
            if "error" in data or "message" in data:
                error_msg = data.get("error") or data.get("message")
                logging.error(f"API вернул ошибку: {error_msg}")
                return {"days": []}
            
            schedule_data = data.get("schedule", {})
            if not schedule_data or not isinstance(schedule_data, dict):
                logging.warning("В ответе API отсутствуют данные расписания")
                return {"days": []}
            
            records = schedule_data.get("records", [])
            if not records:
                logging.warning("API вернул пустой список занятий")
                return {"days": []}
            
            # Группируем занятия по дням
            days_dict = {}
            target_day = target_date.date if hasattr(target_date, 'date') else target_date
            target_date_str = target_day.strftime('%Y%m%d')
            
            for record in records:
                date = record.get("lessonDate")
                if not date:
                    continue
                
                # Для запроса на конкретный день проверяем точное совпадение даты
                if not (hasattr(target_date, 'is_week_request') and target_date.is_week_request):
                    if date != target_date_str:
                        logging.debug(f"Пропускаем занятие на дату {date}, так как ищем на {target_date_str}")
                        continue
                
                # Преобразуем дату из формата YYYYMMDD в YYYY-MM-DD
                formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
                if formatted_date not in days_dict:
                    days_dict[formatted_date] = []
                
                # Преобразуем запись занятия в нужный формат
                lesson = {
                    "number": record.get("lessonNum", ""),
                    "timeStart": record.get("lessonTimeStart", ""),
                    "timeEnd": record.get("lessonTimeEnd", ""),
                    "subject": {
                        "title": record.get("lessonSubject", {}).get("subjectTitle", "")
                    },
                    "teacher": {
                        "title": record.get("lessonLecturers", [{}])[0].get("lecturerName", "")
                    },
                    "classroom": {
                        "title": f"{record.get('lessonRoom', {}).get('roomTitle', '')} {record.get('lessonBuilding', {}).get('buildingCode', '')}"
                    }
                }
                
                # Добавляем комментарий к занятию, если он есть
                commentary = record.get("lessonCommentary")
                if commentary:
                    lesson["commentary"] = commentary
                
                days_dict[formatted_date].append(lesson)
            
            # Преобразуем словарь дней в список
            days = [{"date": date, "lessons": lessons} for date, lessons in sorted(days_dict.items())]
            
            logging.info(f"Сформировано {len(days)} дней с занятиями")
            if days:
                logging.info(f"Пример первого дня: {days[0]}")
            else:
                logging.warning("Не найдено занятий после фильтрации")
            
            return {"days": days}
        else:
            logging.error(f"Неожиданный формат данных от API: {type(data)}")
            return {"days": []}
            
    except httpx.HTTPError as e:
        logging.error(f"Ошибка HTTP при получении расписания: {e}")
        raise
    except ValueError as e:
        logging.error(f"Ошибка при разборе JSON расписания: {e}")
        raise
    except Exception as e:
        logging.error(f"Неожиданная ошибка при получении расписания: {str(e)}")
        raise

async def get_group_name(schedule: Schedule) -> Optional[str]:
    url: str = schedule.get_schedule_url()
    url += f"&file=list.json&api_token={TOKEN}"

    try:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get("group", {}).get("name")
    except (httpx.HTTPError, ValueError) as e:
        logging.error(f"Ошибка при получении имени группы: {e}")
        return None

