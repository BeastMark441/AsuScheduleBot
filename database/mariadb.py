import logging
from typing import Any, Optional, TYPE_CHECKING, TypedDict, Union
from datetime import datetime, timedelta, date
import mariadb
from functools import lru_cache
from cachetools import TTLCache
import json

if TYPE_CHECKING:
    from asu.timetable import TimeTable

class UserData(TypedDict):
    user_id: int
    username: Optional[str]
    group_name: Optional[str]
    lecturer_name: Optional[str]
    report_denied: bool

class MariaDB:
    _instance = None
    _is_initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, host: str, user: str, password: str, database: str):
        if self._is_initialized:
            return
            
        self.config = {
            'host': host,
            'user': user,
            'password': password,
            'database': database
        }
        
        try:
            self.pool = mariadb.ConnectionPool(
                pool_name='mypool',
                pool_size=20,
                **self.config
            )
        except mariadb.ProgrammingError as e:
            if "Pool 'mypool' already exists" in str(e):
                # Если пул уже существует, получаем его
                self.pool = mariadb.ConnectionPool(pool_name='mypool')
            else:
                raise
        
        # Создаем отдельные кеши для разных типов данных
        self._user_cache = TTLCache(maxsize=2000, ttl=600)  # 10 минут, больше записей
        self._group_cache = TTLCache(maxsize=2000, ttl=300)  # 5 минут
        self._users_list_cache = TTLCache(maxsize=1, ttl=60)  # 1 минута для списка всех пользователей
        self._schedule_cache = TTLCache(maxsize=500, ttl=3600)  # 1 час для расписаний
        
        # Добавляем bulk операции
        self._cache_queue = []
        self._queue_size = 100
        
        self._create_tables()
        self._is_initialized = True
        logging.info("MariaDB connection established")

    def _create_tables(self) -> None:
        """Создание необходимых таблиц"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(32),
                    group_name VARCHAR(50),
                    lecturer_name VARCHAR(100),
                    report_denied BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_username (username),
                    INDEX idx_group (group_name),
                    INDEX idx_lecturer (lecturer_name)
                ) ENGINE=InnoDB
            ''')

            # Таблица заметок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notes (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    subject VARCHAR(100) NOT NULL,
                    note_text TEXT NOT NULL,
                    note_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_chat (user_id, chat_id),
                    INDEX idx_note_date (note_date),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                ) ENGINE=InnoDB
            ''')

            # Таблица кеша расписаний
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schedule_cache (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    query_type ENUM('group', 'lecturer') NOT NULL,
                    query_text VARCHAR(100) NOT NULL,
                    result_data JSON,
                    path VARCHAR(255),
                    is_found BOOLEAN NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_query (query_type, query_text),
                    INDEX idx_created (created_at)
                ) ENGINE=InnoDB
            ''')

            # Таблица кеша расписаний на конкретные даты
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS timetable_cache (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    schedule_cache_id BIGINT NOT NULL,
                    date_start DATE NOT NULL,
                    date_end DATE,
                    timetable_data JSON NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_schedule_date (schedule_cache_id, date_start, date_end),
                    INDEX idx_created (created_at),
                    FOREIGN KEY (schedule_cache_id) REFERENCES schedule_cache(id) ON DELETE CASCADE
                ) ENGINE=InnoDB
            ''')

            # Таблица статистики
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS statistics (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    event_type VARCHAR(50) NOT NULL,
                    user_id BIGINT,
                    chat_id BIGINT,
                    command VARCHAR(50),
                    query_text VARCHAR(255),
                    response_time FLOAT,
                    success BOOLEAN,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    extra_data JSON,
                    INDEX idx_event (event_type),
                    INDEX idx_user (user_id),
                    INDEX idx_command (command),
                    INDEX idx_created (created_at)
                ) ENGINE=InnoDB
            ''')

            # Таблица агрегированной статистики по дням
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_statistics (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    date DATE NOT NULL,
                    total_requests INT DEFAULT 0,
                    unique_users INT DEFAULT 0,
                    successful_requests INT DEFAULT 0,
                    failed_requests INT DEFAULT 0,
                    avg_response_time FLOAT DEFAULT 0,
                    most_used_commands JSON,
                    most_searched_groups JSON,
                    most_searched_lecturers JSON,
                    UNIQUE INDEX idx_date (date)
                ) ENGINE=InnoDB
            ''')

            conn.commit()

    def get_user(self, user_id: int) -> Optional[UserData]:
        """Получение информации о пользователе с кешированием"""
        cache_key = f"user_{user_id}"
        if cache_key in self._user_cache:
            return self._user_cache[cache_key]

        with self.pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                'SELECT * FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            if result:
                typed_result: UserData = {
                    'user_id': result['user_id'],
                    'username': result['username'],
                    'group_name': result['group_name'],
                    'lecturer_name': result['lecturer_name'],
                    'report_denied': bool(result['report_denied'])
                }
                self._user_cache[cache_key] = typed_result
                return typed_result
            return None

    def save_user(self, user_id: int, username: str | None) -> None:
        """Сохранение информации о пользователе"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (user_id, username)
                VALUES (?, ?)
                ON DUPLICATE KEY UPDATE username = ?
            ''', (user_id, username, username))
            conn.commit()
            
        # Инвалидируем кеши
        cache_key = f"user_{user_id}"
        self._user_cache.pop(cache_key, None)
        self._users_list_cache.clear()

    def get_group(self, user_id: int) -> str | None:
        """Получение группы пользователя с кешированием"""
        cache_key = f"group_{user_id}"
        if cache_key in self._group_cache:
            return self._group_cache[cache_key]

        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT group_name FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            if result:
                self._group_cache[cache_key] = result[0]
            return result[0] if result else None

    def save_group(self, user_id: int, group_name: str) -> None:
        """Сохранение группы пользователя"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (user_id, group_name)
                VALUES (?, ?)
                ON DUPLICATE KEY UPDATE group_name = ?
            ''', (user_id, group_name, group_name))
            conn.commit()
            
        # Инвалидируем кеши
        cache_key = f"group_{user_id}"
        self._group_cache.pop(cache_key, None)
        self._user_cache.pop(f"user_{user_id}", None)
        self._users_list_cache.clear()

    def get_all_users(self) -> list[tuple[int, str | None, str | None, str | None]]:
        """Получение списка всех пользователей с кешированием"""
        cache_key = "all_users"
        if cache_key in self._users_list_cache:
            return self._users_list_cache[cache_key]

        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT user_id, username, group_name, lecturer_name FROM users'
            )
            result = cursor.fetchall()
            self._users_list_cache[cache_key] = result
            return result

    def cleanup_old_notes(self) -> None:
        """Удаление старых заметок"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM notes 
                WHERE note_date < DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)
            ''')
            conn.commit()

    def clear_caches(self) -> None:
        """Очистка всех кешей"""
        self._user_cache.clear()
        self._group_cache.clear()
        self._users_list_cache.clear() 

    def get_cached_schedule(self, query_type: str, query_text: str) -> Optional[dict[str, Any]]:
        """Получение кешированного результата поиска расписания"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT * FROM schedule_cache 
                WHERE query_type = ? AND query_text = ? 
                AND created_at > DATE_SUB(NOW(), INTERVAL 1 DAY)
            ''', (query_type, query_text))
            return cursor.fetchone()

    def cache_schedule(self, query_type: str, query_text: str, 
                      result_data: dict[str, Any] | None, 
                      path: str | None, is_found: bool) -> int:
        """Кеширование результата поиска расписания"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO schedule_cache 
                (query_type, query_text, result_data, path, is_found)
                VALUES (?, ?, ?, ?, ?)
            ''', (query_type, query_text, json.dumps(result_data) if result_data else None, 
                 path, is_found))
            conn.commit()
            if cursor.lastrowid is None:
                raise ValueError("Failed to get last insert ID")
            return cursor.lastrowid

    def get_cached_timetable(self, schedule_cache_id: int, date_start: date, 
                           date_end: date | None) -> Optional[dict[str, Any]]:
        """Получение кешированного расписания на конкретные даты"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            if date_end:
                cursor.execute('''
                    SELECT * FROM timetable_cache 
                    WHERE schedule_cache_id = ? AND date_start = ? AND date_end = ?
                    AND created_at > DATE_SUB(NOW(), INTERVAL 1 DAY)
                ''', (schedule_cache_id, date_start, date_end))
            else:
                cursor.execute('''
                    SELECT * FROM timetable_cache 
                    WHERE schedule_cache_id = ? AND date_start = ? AND date_end IS NULL
                    AND created_at > DATE_SUB(NOW(), INTERVAL 1 DAY)
                ''', (schedule_cache_id, date_start))
            return cursor.fetchone()

    def cache_timetable(self, schedule_cache_id: int, date_start: date, 
                       date_end: date | None, timetable: 'TimeTable') -> None:
        """Кеширование расписания на конкретные дты"""
        serialized_data = timetable.to_dict()
        
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO timetable_cache 
                (schedule_cache_id, date_start, date_end, timetable_data)
                VALUES (?, ?, ?, ?)
            ''', (schedule_cache_id, date_start, date_end, json.dumps(serialized_data)))
            conn.commit()

    def cleanup_cache(self) -> None:
        """Очистка устаревшего кеша"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            # Удаляем записи старше 24 часов
            cursor.execute('''
                DELETE FROM schedule_cache 
                WHERE created_at < DATE_SUB(NOW(), INTERVAL 1 DAY)
            ''')
            conn.commit()

    def is_report_denied(self, user_id: int) -> bool:
        """Проверяет, заблокирован ли пользователь для отправки report"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT report_denied FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            return bool(result[0]) if result else False

    def set_report_denied(self, user_id: int, denied: bool) -> None:
        """Устанавливает блокировку report для пользователя"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (user_id, report_denied)
                VALUES (?, ?)
                ON DUPLICATE KEY UPDATE report_denied = ?
            ''', (user_id, denied, denied))
            conn.commit()
            
            # Инвалидируем кеш пользователя
            cache_key = f"user_{user_id}"
            self._user_cache.pop(cache_key, None)

    def log_event(self, *args) -> None:
        """Логирование с накоплением"""
        self._cache_queue.append(args)
        if len(self._cache_queue) >= self._queue_size:
            self.bulk_save()

    def bulk_save(self) -> None:
        """Сохранение накопленных данных одним запросом"""
        if not self._cache_queue:
            return
            
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                'INSERT INTO statistics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                self._cache_queue
            )
            conn.commit()
            self._cache_queue.clear()

    def get_daily_statistics(self, start_date: date | None = None, 
                           end_date: date | None = None) -> list[dict[str, Any]]:
        """Получение дневной статистики за период"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            if start_date and end_date:
                cursor.execute('''
                    SELECT * FROM daily_statistics
                    WHERE date BETWEEN ? AND ?
                    ORDER BY date DESC
                ''', (start_date, end_date))
            else:
                cursor.execute('''
                    SELECT * FROM daily_statistics
                    ORDER BY date DESC LIMIT 30
                ''')
            return cursor.fetchall()

    def aggregate_daily_statistics(self) -> None:
        """Агрегация статистики за предыдущий день"""
        yesterday = (datetime.now() - timedelta(days=1)).date()
        
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            
            # Подсчет основных метрик
            cursor.execute('''
                INSERT INTO daily_statistics 
                (date, total_requests, unique_users, successful_requests, 
                 failed_requests, avg_response_time)
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as total_requests,
                    COUNT(DISTINCT user_id) as unique_users,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_requests,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_requests,
                    AVG(response_time) as avg_response_time
                FROM statistics
                WHERE DATE(created_at) = ?
                GROUP BY DATE(created_at)
                ON DUPLICATE KEY UPDATE
                    total_requests = VALUES(total_requests),
                    unique_users = VALUES(unique_users),
                    successful_requests = VALUES(successful_requests),
                    failed_requests = VALUES(failed_requests),
                    avg_response_time = VALUES(avg_response_time)
            ''', (yesterday,))
            
            # Самые используемые команды
            cursor.execute('''
                SELECT command, COUNT(*) as count
                FROM statistics
                WHERE DATE(created_at) = ? AND command IS NOT NULL
                GROUP BY command
                ORDER BY count DESC
                LIMIT 10
            ''', (yesterday,))
            most_used_commands = cursor.fetchall()
            
            # Самые искомые группы
            cursor.execute('''
                SELECT query_text, COUNT(*) as count
                FROM statistics
                WHERE DATE(created_at) = ? AND event_type = 'group_search'
                GROUP BY query_text
                ORDER BY count DESC
                LIMIT 10
            ''', (yesterday,))
            most_searched_groups = cursor.fetchall()
            
            # Самые искомые преподаватели
            cursor.execute('''
                SELECT query_text, COUNT(*) as count
                FROM statistics
                WHERE DATE(created_at) = ? AND event_type = 'lecturer_search'
                GROUP BY query_text
                ORDER BY count DESC
                LIMIT 10
            ''', (yesterday,))
            most_searched_lecturers = cursor.fetchall()
            
            # Обновляем агрегированные данные
            cursor.execute('''
                UPDATE daily_statistics
                SET most_used_commands = ?,
                    most_searched_groups = ?,
                    most_searched_lecturers = ?
                WHERE date = ?
            ''', (
                json.dumps(most_used_commands),
                json.dumps(most_searched_groups),
                json.dumps(most_searched_lecturers),
                yesterday
            ))
            
            conn.commit()
        