import requests
import re
import logging
from bs4 import BeautifulSoup
from md2tgmd import escape

session = requests.Session()

def find_group_url(group_name: str):
    search_url = f"https://www.asu.ru/timetable/search/students/?query={group_name}"
    response = session.get(search_url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        schedule_link = soup.find('a', title='расписание группы')

        if schedule_link:
            return "https://www.asu.ru" + schedule_link['href'] + "?mode=print"

    return None

def get_id(url: str) -> str:
    response = session.get(url)
    pattern = r"'X-CS-ID', '([0-9a-z]{32})'"
    match = re.search(pattern, response.text)

    if not match:
        raise Exception("X-CS-ID не найден в ответе.")

    return match.group(1)

def get_timetable(schedule_url: str) -> str:
    cs_id = get_id(schedule_url)

    custom_headers = {
        "Accept": "*/*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "X-Cs-Id": cs_id,
        "Referer": schedule_url
    }

    print(schedule_url)

    response = session.get(schedule_url, headers=custom_headers)

    if response.status_code != 200:
        return f"Ошибка при получении расписания. Код ошибки {response.status_code}"
    
    return response.text

def translate_pair_number(pair_number: str) -> str:
    emoji_numbers = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]

    if pair_number.isdigit() and int(pair_number) < 10:
        return emoji_numbers[int(pair_number)]
    else:
        return "❓"  # Если номер пары выходит за пределы 0-9

# Функция для форматирования расписания
def format_schedule(response_text: str, schedule_link: str, group_name: str) -> str:
    soup = BeautifulSoup(response_text, 'html.parser')
    timetable = soup.find('table', class_='schedule_table')

    if not timetable:
        return "Расписание не найдено или нет занятий"

    formatted_schedule = []
    formatted_schedule.append(f"📚 Расписание для группы: {group_name}\n🚀 На текущую неделю\n")

    current_date = ""
    days_schedule = {}  # Словарь для группировки расписания по дням

    rows = timetable.find_all('tr', class_='schedule_table-body-row')
    for row in rows:
        date_cell = row.find('td', {'data-type': 'date'})
        if date_cell:
            current_date = date_cell.get_text(strip=True).strip()
            continue

        # Извлечение данных о паре
        pair_number_cell = row.find('td', {'data-type': 'num'})
        time_cell = row.find('td', {'data-type': 'time'})
        subject_cell = row.find('td', {'data-type': 'subject'})
        lecturer_cell = row.find('td', {'data-type': 'lecturer'})
        room_cell = row.find('td', {'data-type': 'room'})
        modify_date_cell = row.find('td', {'data-type': 'modify_date'})
        subtext_cell = row.find('span', class_='schedule_table-subtext')

        date_split: list[str] = [i for i in current_date.strip().split(' ') if i]

        date_stripped = date_split[0] + " " + date_split[1]
        pair_number = pair_number_cell.get_text(strip=True) if pair_number_cell else "Номер пары не указан"
        time = time_cell.get_text(strip=True) if time_cell else "Время не указано"
        subject = subject_cell.get_text(strip=True) if subject_cell else "Предмет не указан"
        lecturer = lecturer_cell.get_text(strip=True) if lecturer_cell else "Преподаватель не указан"
        room = room_cell.get_text(strip=True).strip() if room_cell else "Аудитория не указана"; room = room if room else "ауд не указана"

        # Сноска, если есть
        subtext = subtext_cell.get_text(strip=True) if subtext_cell else ""

        if subtext:
            subject = subject.replace(subtext, '')

        # Форматируем вывод
        formatted_row = (
            f"{translate_pair_number(pair_number)} "
            f"🕑 {time}\n"
            f"📚 {subject}\n"
            f"👩 {lecturer}\n"
            f"🏢 {room}\n"
        )

        if subtext:
            formatted_row += f"🏷️ {subtext}\n"  # Выделяем сноску на отдельной строке

        if date_stripped not in days_schedule:
            days_schedule[date_stripped] = []
        days_schedule[date_stripped].append(formatted_row)

    # Объединяем расписание по дням
    for date, entries in days_schedule.items():
        formatted_schedule.append(f"📅 {date}\n" + "\n".join(entries))

    formatted_schedule.append(f"🚀 [Ссылка на расписание]({schedule_link})")

    result = escape("\n\n".join(formatted_schedule))
    return result