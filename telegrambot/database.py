import sqlite3
import logging

class Database:
    def __init__(self, db_name: str = "bot_database.db") -> None:
        self.conn: sqlite3.Connection = sqlite3.connect(db_name)
        self.cursor: sqlite3.Cursor = self.conn.cursor()
        self.create_tables()
        self.migrate_old_data()

    def create_tables(self) -> None:
        # Таблица пользователей
        _ = self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS users
        (user_id INTEGER PRIMARY KEY,
         username TEXT,
         first_name TEXT,
         last_name TEXT,
         group_name TEXT,
         lecturer_name TEXT,
         first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        ''')
        self.conn.commit()

    def save_user(self, user_id: int, username: str | None, first_name: str | None, last_name: str | None) -> None:
        """Сохраняет или обновляет информацию о пользователе"""
        _ = self.cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name))
        self.conn.commit()

    def save_group(self, user_id: int, group_name: str) -> None:
        """Обновляет информацию о группе пользователя"""
        _ = self.cursor.execute('''
        UPDATE users 
        SET group_name = ?
        WHERE user_id = ?
        ''', (group_name, user_id))
        self.conn.commit()

    def save_lecturer(self, user_id: int, lecturer_name: str) -> None:
        """Обновляет информацию о преподавателе пользователя"""
        _ = self.cursor.execute('''
        UPDATE users 
        SET lecturer_name = ?
        WHERE user_id = ?
        ''', (lecturer_name, user_id))
        self.conn.commit()

    def get_group(self, user_id: int) -> str | None:
        """Получает сохраненную группу пользователя"""
        _ = self.cursor.execute('SELECT group_name FROM users WHERE user_id = ?', (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result and result[0] else None

    def get_lecturer(self, user_id: int) -> str | None:
        """Получает сохраненного преподавателя пользователя"""
        _ = self.cursor.execute('SELECT lecturer_name FROM users WHERE user_id = ?', (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result and result[0] else None

    def clear_group(self, user_id: int) -> None:
        """Очищает информацию о группе пользователя"""
        _ = self.cursor.execute('''
        UPDATE users 
        SET group_name = NULL
        WHERE user_id = ?
        ''', (user_id,))
        self.conn.commit()

    def clear_lecturer(self, user_id: int) -> None:
        """Очищает информацию о преподавателе пользователя"""
        _ = self.cursor.execute('''
        UPDATE users 
        SET lecturer_name = NULL
        WHERE user_id = ?
        ''', (user_id,))
        self.conn.commit()

    def get_all_users(self) -> list[tuple]:
        """Получает список всех пользователей с их данными"""
        cursor = self.cursor.execute('SELECT user_id, username, first_name, last_name, group_name, lecturer_name FROM users')
        return cursor.fetchall()

    def close(self) -> None:
        self.conn.close()

    def migrate_old_data(self) -> None:
        """Миграция данных из старых таблиц в новую"""
        try:
            # Проверяем существование старых таблиц
            old_tables = self.cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND (name='user_groups' OR name='user_lecturers')
            """).fetchall()
            
            if not old_tables:
                return
                
            # Получаем данные из старых таблиц
            groups = self.cursor.execute('SELECT user_id, group_name FROM user_groups').fetchall()
            lecturers = self.cursor.execute('SELECT user_id, lecturer_name FROM user_lecturers').fetchall()
            
            # Переносим данные в новую таблицу
            for user_id, group_name in groups:
                self.cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, group_name)
                VALUES (?, ?)
                ''', (user_id, group_name))
                
            for user_id, lecturer_name in lecturers:
                self.cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, lecturer_name)
                VALUES (?, ?)
                ''', (user_id, lecturer_name))
            
            # Удаляем старые таблицы
            self.cursor.execute('DROP TABLE IF EXISTS user_groups')
            self.cursor.execute('DROP TABLE IF EXISTS user_lecturers')
            
            self.conn.commit()
            logging.info("Миграция данных успешно завершена")
            
        except Exception as e:
            logging.error(f"Ошибка при миграции данных: {e}")
            self.conn.rollback()
