from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from bs4 import BeautifulSoup
import requests
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Функция для поиска расписания
def find_schedule(group_name):
    search_url = f"https://www.asu.ru/timetable/search/students/?query={group_name}"
    response = requests.get(search_url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        schedule_link = soup.find('a', title='расписание группы')

        if schedule_link:
            return "https://www.asu.ru" + schedule_link['href']
        else:
            return "Группа не найдена."
    else:
        return "Ошибка при поиске расписания."

# Функция для получения расписания
def get_timetable(schedule_url):
    driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()))
    
    driver.get(schedule_url)  # Переход по ссылке
    page_source = driver.page_source
    driver.quit()

    soup = BeautifulSoup(page_source, 'html.parser')
    timetable_container = soup.find('div', id='timetable-container')

    if timetable_container:
        return timetable_container  # Получаем весь контейнер с расписанием
    else:
        return "Расписание не найдено."

def translate_pair_number(pair_number):
    emoji_numbers = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
    
    if pair_number.isdigit() and int(pair_number) < 10:
        return emoji_numbers[int(pair_number)]
    else:
        return "❓"  # Если номер пары выходит за пределы 0-9

# Функция для форматирования расписания
def format_schedule(timetable, schedule_link, group_name):
    formatted_schedule = []
    
    # Заголовок с информацией о группе и неделе
    formatted_schedule.append(f"📚 Расписание для группы: {group_name}\n🚀 На текущую неделю\n")
    
    date_groups = timetable.find_all('div', class_='schedule_table-body-rows_group')
    
    for group in date_groups:
        date = group.find('span', class_='schedule_table-date')
        day = date.find('span', class_='schedule_table-date-wd').get_text(strip=True)
        month_day = date.find('span', class_='schedule_table-date-dm').get_text(strip=True)
        formatted_schedule.append(f"📅 {day} {month_day}")

        rows = group.find('div', class_='schedule_table-body-rows_group-rows').find_all('div', class_='schedule_table-body-row')

        for row in rows:
            pair_number_cell = row.find('div', {'data-type': 'num'})
            if not pair_number_cell or not pair_number_cell.get_text(strip=True):
                continue

            time_cell = row.find('div', {'data-type': 'time'})
            subject_cell = row.find('div', {'data-type': 'subject'})
            lecturer_cell = row.find('div', {'data-type': 'lecturer'})
            room_cell = row.find('div', {'data-type': 'room'})
            subtext_cell = row.find('span', class_='schedule_table-subtext')

            pair_number = pair_number_cell.get_text(strip=True) if pair_number_cell else "Номер пары не указан"
            time = time_cell.get_text(strip=True) if time_cell else "Время не указано"
            subject = subject_cell.get_text(strip=True) if subject_cell else "Предмет не указан"
            lecturer = lecturer_cell.get_text(strip=True) if lecturer_cell else "Преподаватель не указан"
            room = room_cell.get_text(strip=True) if room_cell else "Аудитория не указана"
            subtext = subtext_cell.get_text(strip=True) if subtext_cell else ""

            # Удаляем сноску из названия предмета, если она присутствует
            if subtext and subject.endswith(subtext):
                subject = subject[:-len(subtext)].strip()

            # Форматируем вывод
            formatted_row = (
                f"{translate_pair_number(pair_number)}\n"
                f"🕑 {time}\n"
                f"📚 {subject}\n"
            )

            # Добавляем сноску, если она есть
            if subtext:
                formatted_row += f"🏷️ {subtext}\n"
                
            formatted_row += f"👩‍🏫 {lecturer} (преп.)\n"
            formatted_row += f"🏢 {room}\n"
            
            formatted_schedule.append(formatted_row)

    formatted_schedule.append(f"🚀 Ссылка на расписание\n({schedule_link})")
    return "\n\n".join(formatted_schedule)

# Обработчик команд /schedule
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text('Пожалуйста, введите название группы. Например: /schedule 305с11-4')
        return

    group_name = context.args[0]  # Получаем название группы
    await update.message.reply_text(f'Ищу расписание для группы: {group_name}...')

    schedule_url = find_schedule(group_name)

    if "http" in schedule_url:
        timetable = await asyncio.to_thread(get_timetable, schedule_url)  # Запускаем в отдельном потоке
        if isinstance(timetable, str):  # Если расписание не найдено
            await update.message.reply_text(timetable)
        else:
            formatted_timetable = format_schedule(timetable, schedule_url, group_name)  # Передаем название группы
            
            # Отправляем отформатированное расписание
            await update.message.reply_text(formatted_timetable)
    else:
        await update.message.reply_text(schedule_url)

# Основная функция
def main():
    TOKEN = 'YOUR_BOT_TOKEN'  # Укажите ваш токен бота
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Добавляем обработчик команды /schedule
    application.add_handler(CommandHandler('schedule', schedule))
    
    application.run_polling()

if __name__ == '__main__':
    main()
