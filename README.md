# AsuScheduleBot
Бот для телеграм для поиска расписания студентам и преподавателям

## Установка

1. Клонируйте репозиторий:
    ```bash
    git clone https://github.com/BeastMark441/shudlebotasu.git
    ```
2. Перейдите в директорию проекта:
    ```bash
    cd shudlebotasu
    ```
3. Установите зависимости:
    ```bash
    apt install python
    ```
    ```bash
    pip install -r requirements.txt
    ```

## Использование

Не забудьте поменять токен бота на Ваш в файле Token.txt
```python
TOKEN = 'YOUR_BOT_TOKEN'
```

# Запуск бота
```bash
python3 ./bot.py
```

# Команды бота
``/start`` - Запустить/Перезарустить бота.

``/schedule [номер группы]`` - поиск расписания по номеру группы
