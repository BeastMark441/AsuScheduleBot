from datetime import datetime
from typing import Dict, List, Optional

from frozenlist import FrozenList
from md2tgmd import escape as escape_markdown
from bs4 import BeautifulSoup, Tag

def __extract_text(cell: Optional[Tag], default: str) -> str:
    return cell.get_text(strip=True, separator=' ').strip() if cell else default

_weekdays = FrozenList(["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"])
def __get_weekday(weekday: int) -> str:
    if weekday >= len(_weekdays):
        return ""
    
    return _weekdays[weekday]

_emoji_numbers = FrozenList(("0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"))
def __num_to_emoji(num: str) -> str:
    if num.isdigit() and (int(num) - 1) < len(_emoji_numbers):
        return _emoji_numbers[int(num) - 1]
    
    return "❓"

def format_schedule(response_text: str, schedule_link: str, group_name: str, target_date: Optional[datetime] = None) -> str:
    soup = BeautifulSoup(response_text, 'html.parser')
    timetable = soup.find('table', class_='schedule_table')

    if not timetable or not isinstance(timetable, Tag):
        return "Расписание не найдено или нет занятий"

    formatted_schedule = [f"📚 Расписание для группы: {group_name}\n"]
    current_date = datetime.now()
    days_schedule: Dict[datetime, List[str]] = {}

    row: Tag
    for row in timetable.find_all_next('tr', class_='schedule_table-body-row'): # type: ignore
        date_cell = row.find('td', {'data-type': 'date'})
        if date_cell:
            current_date = datetime.strptime(
                date_cell.get_text(strip=True).split()[1], "%d.%m.%Y")

            continue

        # Извлечение данных о паре
        pair_number = __extract_text(row.find('td', {'data-type': 'num'}), "Номер пары не указан") # type: ignore
        time = __extract_text(row.find('td', {'data-type': 'time'}), "Время не указано") # type: ignore
        subject = __extract_text(row.find('td', {'data-type': 'subject'}), "Предмет не указан") # type: ignore
        lecturer = __extract_text(row.find('td', {'data-type': 'lecturer'}), "Преподаватель не указан") # type: ignore
        room = __extract_text(row.find('td', {'data-type': 'room'}), "Аудитория не указана") # type: ignore
        subtext = __extract_text(row.find('span', class_='schedule_table-subtext'), "") # type: ignore

        if subtext:
            subject = subject.replace(subtext, '')

        formatted_row = (
            f"{__num_to_emoji(pair_number)}🕑 {time}\n"
            f"📚 {subject}\n"
            f"👩 {lecturer}\n"
            f"🏢 {room}\n"
        )

        if subtext:
            formatted_row += f"🏷️ {subtext}\n"

        days_schedule.setdefault(current_date, []).append(formatted_row)

    for date, entries in days_schedule.items():
        if not target_date or date.date() == target_date.date():
            formatted_schedule.append(f"📅 {__get_weekday(date.weekday())} {date.strftime('%d.%m')}\n" + "\n".join(entries))

    formatted_schedule.append(f"🚀 [Ссылка на расписание]({schedule_link})")
    
    return escape_markdown("\n\n".join(formatted_schedule))

