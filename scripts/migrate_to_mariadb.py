import os
import sys
import sqlite3
import logging
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from database.mariadb import MariaDB
from config.database import MARIADB_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_data():
    """Миграция данных из SQLite в MariaDB"""
    sqlite_conn = None
    try:
        # Подключаемся к SQLite
        sqlite_path = Path(project_root) / 'bot_database.db'
        if not sqlite_path.exists():
            logger.error(f"SQLite database not found at {sqlite_path}")
            return
            
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_cursor = sqlite_conn.cursor()
        
        # Инициализируем MariaDB
        mariadb = MariaDB(**MARIADB_CONFIG)
        
        # Мигрируем пользователей
        logger.info("Migrating users...")
        sqlite_cursor.execute('SELECT * FROM users')
        users = sqlite_cursor.fetchall()
        
        with mariadb.pool.get_connection() as conn:
            cursor = conn.cursor()
            for user in users:
                cursor.execute('''
                    INSERT INTO users (user_id, username, group_name, lecturer_name, report_denied)
                    VALUES (?, ?, ?, ?, ?)
                    ON DUPLICATE KEY UPDATE
                        username = VALUES(username),
                        group_name = VALUES(group_name),
                        lecturer_name = VALUES(lecturer_name),
                        report_denied = VALUES(report_denied)
                ''', user)
            conn.commit()
        
        # Мигрируем заметки
        logger.info("Migrating notes...")
        sqlite_cursor.execute('SELECT * FROM notes')
        notes = sqlite_cursor.fetchall()
        
        with mariadb.pool.get_connection() as conn:
            cursor = conn.cursor()
            for note in notes:
                cursor.execute('''
                    INSERT INTO notes (id, user_id, chat_id, subject, note_text, note_date, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON DUPLICATE KEY UPDATE
                        user_id = VALUES(user_id),
                        chat_id = VALUES(chat_id),
                        subject = VALUES(subject),
                        note_text = VALUES(note_text),
                        note_date = VALUES(note_date)
                ''', note)
            conn.commit()
        
        logger.info("Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        if sqlite_conn:
            sqlite_conn.close()

if __name__ == "__main__":
    migrate_data() 