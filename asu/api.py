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
    
    try:
        response = await client.get(search_url)
        response.raise_for_status()
        json = response.json()
    except httpx.HTTPError as e:
        logging.error(f"Ошибка HTTP при поиске расписания: {e}")
        return None
    except ValueError as e:
        logging.error(f"Ошибка при разборе JSON: {e}")
        return None

    if "error" in json or "message" in json:
        logging.warning(json.get("error") or json.get("message"))
        return None

    groups = json.get("groups", {})
    if not groups or int(groups.get("rows", 0)) == 0:
        return None

    records = groups.get("records", [])
    if not records:
        return None

    record = records[0]
    faculty_id = record["path"].split("/")[0]
    return Schedule(record["groupCode"], faculty_id, record["groupId"])

async def get_timetable(schedule: Schedule, target_date: Optional[datetime] = None) -> Dict:
    url = schedule.get_schedule_url()
    if target_date:
        # Если запрашивается конкретная неделя, добавляем параметр date
        start_of_week = target_date - timedelta(days=target_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        date_param = f"date={start_of_week.strftime('%Y%m%d')}-{end_of_week.strftime('%Y%m%d')}"
        url = f"{url}&{date_param}"
    
    url += f"&file=list.json&api_token={TOKEN}"
    logging.info(f"Запрашиваем расписание по URL: {url}")

    try:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        logging.info(f"Получены данные расписания: {data}")
        return data
    except httpx.HTTPError as e:
        logging.error(f"Ошибка HTTP при получении расписания: {e}")
        raise
    except ValueError as e:
        logging.error(f"Ошибка при разборе JSON расписания: {e}")
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
