from datetime import datetime
from typing import Dict, List, Optional, Union

from frozenlist import FrozenList
from bs4 import BeautifulSoup, NavigableString, Tag

def __extract_text(cell: Union[Tag, NavigableString, None], default: str) -> str:
    return cell.get_text(strip=True, separator=' ').strip() if cell else default

_weekdays = FrozenList(["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"])
def __get_weekday(weekday: int) -> str:
    if weekday >= len(_weekdays):
        return ""
    
    return _weekdays[weekday]

_emoji_numbers = FrozenList(("0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"))
def __num_to_emoji(num: str) -> str:
    if num.isdigit() and int(num) < len(_emoji_numbers):
        return _emoji_numbers[int(num)]
    
    return "❓"

def escape_markdown(markdown: str) -> str:
    from telegram.helpers import escape_markdown as escape_markdown2
    return escape_markdown2(markdown, version=2)

def format_schedule(response_text: str, schedule_link: str, group_name: str, target_date: Optional[datetime] = None) -> str:
    soup = BeautifulSoup(response_text, 'html.parser')
    timetable = soup.find('table', class_='schedule_table')

    if not timetable or not isinstance(timetable, Tag):
        return "Расписание не найдено или нет занятий"

    formatted_schedule = [f"📚 Расписание для группы: {escape_markdown(group_name)}\n"]
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
        pair_number = __extract_text(row.find('td', {'data-type': 'num'}), "Номер пары не указан")
        time = __extract_text(row.find('td', {'data-type': 'time'}), "Время не указано")
        subject = __extract_text(row.find('td', {'data-type': 'subject'}), "Предмет не указан")
        lecturer = __extract_text(row.find('td', {'data-type': 'lecturer'}), "Преподаватель не указан")
        room = __extract_text(row.find('td', {'data-type': 'room'}), "Аудитория не указана")
        subtext = __extract_text(row.find('span', class_='schedule_table-subtext'), "")

        if subtext:
            subject = subject.replace(subtext, '')

        formatted_row = (
            f"{__num_to_emoji(pair_number)}🕑 {escape_markdown(time)}\n"
            f"📚 {escape_markdown(subject)}\n"
            f"👩 {escape_markdown(lecturer)}\n"
            f"🏢 {escape_markdown(room)}\n"
        )

        if subtext:
            formatted_row += f"🏷️ {escape_markdown(subtext)}\n"

        days_schedule.setdefault(current_date, []).append(formatted_row)

    for date, entries in days_schedule.items():
        if not target_date or date.date() == target_date.date():
            formatted_schedule.append(f"📅 {__get_weekday(date.weekday())} {escape_markdown(date.strftime('%d.%m'))}\n" + "\n".join(entries))

    formatted_schedule.append(f"🚀 [Ссылка на расписание]({schedule_link})")
    
    return "\n\n".join(formatted_schedule)

