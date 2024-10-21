import requests
import re
import logging
from .group import Schedule
from bs4 import BeautifulSoup
from md2tgmd import escape
from datetime import datetime, timedelta, time
from typing import Optional, Union

session = requests.Session()

def find_schedule_url(group_name: str) -> Schedule | None:
    search_url = f"https://www.asu.ru/timetable/search/students/?query={group_name}&mode=print"
    response = session.get(search_url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        schedule_link = soup.find('a', title='расписание группы')

        pattern = r"\/timetable\/students\/([0-9]+)\/([0-9]+)"
        match = re.search(pattern, schedule_link['href'])

        if schedule_link:
            return Schedule(schedule_link.get_text(strip=True), match.group(1), match.group(2))

    return None

def __get_id(url: str) -> str:
    response = session.get(url)
    pattern = r"'X-CS-ID', '([0-9a-z]{32})'"
    match = re.search(pattern, response.text)

    if not match:
        raise Exception("X-CS-ID не найден в ответе.")

    return match.group(1)

def get_timetable(schedule_url: str) -> str | int:
    cs_id = __get_id(schedule_url)

    custom_headers = {
        "Accept": "*/*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "X-Cs-Id": cs_id,
        "Referer": schedule_url
    }

    response = session.get(schedule_url, headers=custom_headers)

    if response.status_code != 200:
        return response.status_code
    
    return response.text

def __translate_pair_number(pair_number: str) -> str:
    emoji_numbers = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]

    if pair_number.isdigit() and int(pair_number) < 10:
        return emoji_numbers[int(pair_number)]
    else:
        return "❓"  # Если номер пары выходит за пределы 0-9
    
def __get_weekday(weekday_num: int) -> str:
    weekdays = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

    if weekday_num >= len(weekdays):
        return ""
    
    return weekdays[weekday_num]

def format_schedule(response_text: str, schedule_link: str, group_name: str, target_date: Optional[datetime]=None) -> str:
    soup = BeautifulSoup(response_text, 'html.parser')
    timetable = soup.find('table', class_='schedule_table')

    if not timetable:
        return "Расписание не найдено или нет занятий"

    formatted_schedule = []
    #formatted_date = target_date.strftime(format='%d.%m.%Y') if target_date else f"{datetime.now().strftime(format='%d.%m.%Y')} {(datetime.now() + timedelta(days=7)).strftime(format='%d.%m.%Y')}"
    formatted_schedule.append(f"📚 Расписание для группы: {group_name}\n")

    current_date: datetime = datetime.now()
    days_schedule: dict[datetime, list[str]] = {}  # Словарь для группировки расписания по дням

    rows = timetable.find_all('tr', class_='schedule_table-body-row')
    for row in rows:
        date_cell = row.find('td', {'data-type': 'date'})
        if date_cell:
            date_split = list(filter(None, date_cell.get_text(strip=True).strip().split(' ')))
            current_date = datetime.strptime(date_split[1], "%d.%m.%Y")
            continue

        # Извлечение данных о паре
        pair_number_cell = row.find('td', {'data-type': 'num'})
        time_cell = row.find('td', {'data-type': 'time'})
        subject_cell = row.find('td', {'data-type': 'subject'})
        lecturer_cell = row.find('td', {'data-type': 'lecturer'})
        room_cell = row.find('td', {'data-type': 'room'})
        subtext_cell = row.find('span', class_='schedule_table-subtext')

        pair_number = pair_number_cell.get_text(strip=True) if pair_number_cell else "Номер пары не указан"
        time = time_cell.get_text(strip=True) if time_cell else "Время не указано"
        subject = subject_cell.get_text(strip=True) if subject_cell else "Предмет не указан"
        lecturer = lecturer_cell.get_text(strip=True) if lecturer_cell else "Преподаватель не указан"
        room = room_cell.get_text(strip=True).strip() if room_cell else "Аудитория не указана"; room = room if room else "Аудитория не указана"

        # Сноска, если есть
        subtext = subtext_cell.get_text(strip=True) if subtext_cell else ""

        if subtext:
            subject = subject.replace(subtext, '')

        # Форматируем вывод
        formatted_row = (
            f"{__translate_pair_number(pair_number)}🕑 {time}\n"
            f"📚 {subject}\n"
            f"👩 {lecturer}\n"
            f"🏢 {room}\n"
        )

        if subtext:
            formatted_row += f"🏷️ {subtext}\n"

        if current_date not in days_schedule:
            days_schedule[current_date] = []
        days_schedule[current_date].append(formatted_row)

    # Объединяем расписание по дням
    for date, entries in days_schedule.items():
        if not target_date or date.date() == target_date.date():
            formatted_schedule.append(f"📅 {__get_weekday(date.weekday())} {date.strftime('%d.%m')}\n" + "\n".join(entries))

    formatted_schedule.append(f"🚀 [Ссылка на расписание]({schedule_link})")

    result = escape("\n\n".join(formatted_schedule))
    return result