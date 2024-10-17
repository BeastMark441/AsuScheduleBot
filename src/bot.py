from typing import List, Tuple
import requests
import re
from bs4 import BeautifulSoup
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Функция для поиска расписания
def find_schedule(group_name: str):
    search_url = f"https://www.asu.ru/timetable/search/students/?query={group_name}"
    response = requests.get(search_url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        schedule_link = soup.find('a', title='расписание группы')

        if schedule_link:
            return "https://www.asu.ru" + schedule_link['href'] + "?mode=print"
        else:
            return "Группа не найдена."
    else:
        return "Ошибка при поиске расписания."

def get_cs_id(session: requests.Session, url: str) -> str:
    response = session.get(url)
    pattern = r"'X-CS-ID', '([0-9a-z]{32})'"
    match = re.search(pattern, response.text)

    if not match:
        raise Exception("CS-ID не найден в ответе.")

    return match.group(1)

def get_timetable(schedule_url: str) -> str:
    session = requests.Session()
    cs_id = get_cs_id(session, schedule_url)

    custom_headers = {
        "X-CS-ID": cs_id,
        "referer": schedule_url
    }

    response = session.get(schedule_url, headers=custom_headers)

    if response.status_code != 200:
        return "Ошибка при получении расписания."

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
        return "Расписание не найдено."

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

        date_stripped = current_date.replace('\n', '').strip()  # Удаление лишних пробелов в дате
        pair_number = pair_number_cell.get_text(strip=True) if pair_number_cell else "Номер пары не указан"
        time = time_cell.get_text(strip=True) if time_cell else "Время не указано"
        subject = subject_cell.get_text(strip=True) if subject_cell else "Предмет не указан"
        lecturer = lecturer_cell.get_text(strip=True) if lecturer_cell else "Преподаватель не указан"
        room = room_cell.get_text(strip=True).strip() if room_cell else "Аудитория не указана"; room = room if room else "ауд не указана"; 
        modify_date = modify_date_cell.get_text(strip=True) if modify_date_cell else "Дата изменения не указана"

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
            #f"✏️ Дата изменения: {modify_date}\n"
        )

        if subtext:
            formatted_row += f"🏷️ {subtext}\n"  # Выделяем сноску на отдельной строке

        if date_stripped not in days_schedule:
            days_schedule[date_stripped] = []
        days_schedule[date_stripped].append(formatted_row)

    # Объединяем расписание по дням
    for date, entries in days_schedule.items():
        formatted_schedule.append(f"📅 {date}\n" + "\n".join(entries))

    formatted_schedule.append(f"🚀 Ссылка на расписание\n({schedule_link})")
    return "\n\n".join(formatted_schedule)

# Обработчик команд /schedule
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text('Пожалуйста, введите название группы. Например: /schedule 305с11-4')
        return

    group_name = context.args[0]
    await update.message.reply_text(f'Ищу расписание для группы: {group_name}...')

    schedule_url = find_schedule(group_name)

    if "http" in schedule_url:
        response_text = await asyncio.to_thread(get_timetable, schedule_url)  # Запускаем в отдельном потоке
        if isinstance(response_text, str) and "Ошибка" in response_text:
            await update.message.reply_text(response_text)
        else:
            formatted_timetable = format_schedule(response_text, schedule_url, group_name)
            await update.message.reply_text(formatted_timetable)
    else:
        await update.message.reply_text(schedule_url)

# Основная функция
def main():
    TOKEN = 'TODO'  # Укажите ваш токен бота

    application = ApplicationBuilder().token(TOKEN).build()

    # Добавляем обработчик команды /schedule
    application.add_handler(CommandHandler('schedule', schedule))

    application.run_polling()

if __name__ == '__main__':
    main()