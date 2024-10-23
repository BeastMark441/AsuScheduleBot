import httpx
import asyncio
import re
import os
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, List, Optional, Union, Any

from .schedule import Schedule

TOKEN = os.getenv("TOKEN_ASU")
client = httpx.AsyncClient()

async def find_schedule_url(group_name: str) -> Optional[Schedule]:
    search_url = f"https://www.asu.ru/timetable/search/students/?query={group_name}&file=list.json&api_token={TOKEN}"
    response = await client.get(search_url)

    json = response.json()

    records = json["groups"]["records"]

    if response and len(records) == 0:
        return None
    
    record = records[0]
    path = record["path"]
    faculty_id = path.split("/")[0]

    return Schedule(record["groupCode"], faculty_id, record["groupId"])

def find_x_cs_id(string: str) -> str:
    pattern = r"'X-CS-ID', '([0-9a-z]{32})'"
    match = re.search(pattern, string)

    if not match:
        raise Exception("X-CS-ID не был найден в запросе.")
    
    return match.group(1)

async def get_timetable(url: str) -> str:
    response = await client.get(url)
    response.raise_for_status()

    id = find_x_cs_id(response.text)
    
    headers = {
        "X-CS-ID": id,
        "Referer": url
    }

    await asyncio.sleep(1)

    response = await client.get(url, headers=headers)
    response.raise_for_status()
    return response.text

async def get_group_name(schedule: Schedule) -> Optional[str]:
    url: str = schedule.get_schedule_url()

    response = await client.get(url)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        return (soup.find("h1")
            .get_text(strip=True)
            .replace("Расписание группы", "")
            .strip())

    return None