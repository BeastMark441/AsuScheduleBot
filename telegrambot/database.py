import sqlite3
import logging
from datetime import date
from config import ADMIN_IDS

class Database:
    def __init__(self, db_name: str = "bot_database.db") -> None:
        self.conn: sqlite3.Connection = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor: sqlite3.Cursor = self.conn.cursor()
        self.cursor.execute('PRAGMA journal_mode=WAL')
        self.cursor.execute('PRAGMA synchronous=NORMAL')
        self.cursor.execute('PRAGMA temp_store=MEMORY')
        self.cursor.execute('PRAGMA cache_size=-2000')
        self.create_tables()
        self.migrate_old_data()
        logging.info("База данных инициализирована")

    def create_tables(self) -> None:
        # Таблица пользователей с username
        _ = self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS users
        (user_id INTEGER PRIMARY KEY,
         username TEXT,
         group_name TEXT,
         lecturer_name TEXT,
         report_denied INTEGER DEFAULT 0)
        ''')
        self.conn.commit()

        # Таблица заметок
        _ = self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         user_id INTEGER NOT NULL,
         chat_id INTEGER NOT NULL,
         subject TEXT NOT NULL,
         note_text TEXT NOT NULL,
         note_date DATE NOT NULL,
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         FOREIGN KEY (user_id) REFERENCES users(user_id))
        ''')
        self.conn.commit()

    def save_user(self, user_id: int, username: str | None) -> None:
        """Сохраняет информацию о пользователе"""
        _ = self.cursor.execute('''
        INSERT INTO users (user_id, username) 
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET username = ?
        ''', (user_id, username, username))
        self.conn.commit()

    def save_group(self, user_id: int, group_name: str) -> None:
        """Обновляет информацию о группе пользователя"""
        _ = self.cursor.execute('''
        INSERT INTO users (user_id, group_name) 
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET group_name = ?
        ''', (user_id, group_name, group_name))
        self.conn.commit()

    def save_lecturer(self, user_id: int, lecturer_name: str) -> None:
        """Обновляет информацию о преподавателе пользователя"""
        _ = self.cursor.execute('''
        INSERT INTO users (user_id, lecturer_name) 
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET lecturer_name = ?
        ''', (user_id, lecturer_name, lecturer_name))
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

    def get_all_users(self) -> list[tuple[int, str | None, str | None, str | None]]:
        """Получает список всех пользователей с их данными"""
        cursor = self.cursor.execute('SELECT user_id, username, group_name, lecturer_name FROM users')
        return cursor.fetchall()

    def close(self) -> None:
        self.conn.close()

    def migrate_old_data(self) -> None:
        """Миграция данных из старых таблиц в новую"""
        try:
            # Проверяем наличие колонки report_denied
            columns = self.cursor.execute("PRAGMA table_info(users)").fetchall()
            column_names = [column[1] for column in columns]
            
            # Если колонки нет, добавляем её
            if 'report_denied' not in column_names:
                logging.info("Добавление колонки report_denied")
                self.cursor.execute('''
                    ALTER TABLE users
                    ADD COLUMN report_denied INTEGER DEFAULT 0
                ''')
                self.conn.commit()
            
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
                self.save_group(user_id, group_name)
                
            for user_id, lecturer_name in lecturers:
                self.save_lecturer(user_id, lecturer_name)
            
            # Удаляем старые таблицы
            self.cursor.execute('DROP TABLE IF EXISTS user_groups')
            self.cursor.execute('DROP TABLE IF EXISTS user_lecturers')
            
            self.conn.commit()
            logging.info("Миграция данных успешно завершена")
            
        except Exception as e:
            logging.error(f"Ошибка при миграции данных: {e}")
            self.conn.rollback()

    def is_report_denied(self, user_id: int) -> bool:
        """Проверяет, заблокирован ли пользователь для отправки report"""
        _ = self.cursor.execute('SELECT report_denied FROM users WHERE user_id = ?', (user_id,))
        result = self.cursor.fetchone()
        return bool(result[0]) if result else False

    def set_report_denied(self, user_id: int, denied: bool) -> None:
        """Устанавливает блокировку report для пользователя"""
        _ = self.cursor.execute('''
        UPDATE users 
        SET report_denied = ?
        WHERE user_id = ?
        ''', (int(denied), user_id))
        self.conn.commit()

    def add_note(self, user_id: int, chat_id: int, subject: str, note_text: str, note_date: date) -> bool:
        """Добавляет новую заметку"""
        try:
            # Проверяем количество заметок пользователя
            if chat_id < 0:  # Групповой чат
                count = self.cursor.execute(
                    'SELECT COUNT(*) FROM notes WHERE chat_id = ?', 
                    (chat_id,)
                ).fetchone()[0]
            else:  # Личный чат
                count = self.cursor.execute(
                    'SELECT COUNT(*) FROM notes WHERE user_id = ? AND chat_id = ?', 
                    (user_id, chat_id)
                ).fetchone()[0]
            
            if count >= 14 and user_id not in ADMIN_IDS:
                return False
            
            self.cursor.execute('''
            INSERT INTO notes (user_id, chat_id, subject, note_text, note_date)
            VALUES (?, ?, ?, ?, ?)
            ''', (user_id, chat_id, subject, note_text, note_date))
            self.conn.commit()
            return True
        except Exception as e:
            logging.error(f"Ошибка при добавлении заметки: {e}")
            return False

    def get_notes(self, user_id: int, chat_id: int, date: date | None = None) -> list[tuple]:
        """Получает заметки пользователя"""
        try:
            if date:
                if chat_id < 0:  # Групповой чат
                    return self.cursor.execute('''
                    SELECT id, subject, note_text, note_date, user_id
                    FROM notes 
                    WHERE chat_id = ? AND note_date = ?
                    ORDER BY note_date
                    ''', (chat_id, date)).fetchall()
                else:  # Личный чат
                    return self.cursor.execute('''
                    SELECT id, subject, note_text, note_date, user_id
                    FROM notes 
                    WHERE user_id = ? AND chat_id = ? AND note_date = ?
                    ORDER BY note_date
                    ''', (user_id, chat_id, date)).fetchall()
            else:
                if chat_id < 0:  # Групповой чат
                    return self.cursor.execute('''
                    SELECT id, subject, note_text, note_date, user_id
                    FROM notes 
                    WHERE chat_id = ?
                    ORDER BY note_date
                    ''', (chat_id,)).fetchall()
                else:  # Личный чат
                    return self.cursor.execute('''
                    SELECT id, subject, note_text, note_date, user_id
                    FROM notes 
                    WHERE user_id = ? AND chat_id = ?
                    ORDER BY note_date
                    ''', (user_id, chat_id)).fetchall()
        except Exception as e:
            logging.error(f"Ошибка при получении заметок: {e}")
            return []

    def delete_note(self, note_id: int, user_id: int) -> bool:
        """Удаляет заметку"""
        try:
            if user_id in ADMIN_IDS:
                self.cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))
            else:
                self.cursor.execute(
                    'DELETE FROM notes WHERE id = ? AND user_id = ?', 
                    (note_id, user_id)
                )
            self.conn.commit()
            return True
        except Exception as e:
            logging.error(f"Ошибка при удалении заметки: {e}")
            return False

    def cleanup_old_notes(self) -> None:
        """Удаляет старые заметки"""
        try:
            self.cursor.execute('''
            DELETE FROM notes 
            WHERE note_date < date('now', '-7 days')
            ''')
            self.conn.commit()
        except Exception as e:
            logging.error(f"Ошибка при очистке старых заметок: {e}")
