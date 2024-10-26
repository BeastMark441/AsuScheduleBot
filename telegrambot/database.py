import sqlite3
from typing import Optional

class Database:
    def __init__(self, db_name: str = "bot_database.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_groups
        (user_id INTEGER PRIMARY KEY, group_name TEXT)
        ''')
        self.conn.commit()

    def save_group(self, user_id: int, group_name: str):
        self.cursor.execute('''
        INSERT OR REPLACE INTO user_groups (user_id, group_name)
        VALUES (?, ?)
        ''', (user_id, group_name))
        self.conn.commit()

    def get_group(self, user_id: int) -> Optional[str]:
        self.cursor.execute('SELECT group_name FROM user_groups WHERE user_id = ?', (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def clear_group(self, user_id: int):
        self.cursor.execute('DELETE FROM user_groups WHERE user_id = ?', (user_id,))
        self.conn.commit()

    def close(self):
        self.conn.close()
