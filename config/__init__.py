from .database import MARIADB_CONFIG
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telegram import Update

# ID администраторов бота (полные права)
BOT_ADMIN_IDS = {983524946, 833357373}

# Права для разных типов администраторов
class AdminRights:
    # Права для администраторов бота
    BOT_ADMIN = {
        'can_broadcast': True,      # Рассылка сообщений
        'can_send_to': True,        # Отправка сообщений конкретным пользователям
        'can_block': True,          # Блокировка пользователей
        'can_unblock': True,        # Разблокировка пользователей
        'can_edit_notes': True,     # Редактирование любых заметок
        'can_delete_notes': True,   # Удаление любых заметок
        'no_notes_limit': True,     # Нет ограничения на количество заметок
        'can_manage_reports': True,  # Управление отчетами об ошибках
        'can_view_stats': True,     # Просмотр статистики
    }
    
    # Права для администраторов чата
    CHAT_ADMIN = {
        'can_broadcast': False,     # Не могут делать рассылку
        'can_send_to': False,       # Не могут отправлять личные сообщения
        'can_block': False,         # Не могут блокировать пользователей
        'can_unblock': False,       # Не могут разблокировать пользователей
        'can_edit_notes': True,     # Могут редактировать заметки в своем чате
        'can_delete_notes': True,   # Могут удалять заметки в своем чате
        'no_notes_limit': False,    # Есть ограничение на количество заметок
        'can_manage_reports': False, # Не могут управлять отчетами об ошибках
        'can_view_stats': False,    # Не могут просматривать статистику
    }

async def check_admin_rights(update: "Update", user_id: int, required_right: str) -> bool:
    """
    Проверяет права администратора
    Args:
        update: Update объект от телеграма
        user_id: ID пользователя
        required_right: Требуемое право (например, 'can_broadcast')
    Returns:
        bool: True если у пользователя есть требуемое право
    """
    # Если пользователь является администратором бота - у него есть все права
    if user_id in BOT_ADMIN_IDS:
        return AdminRights.BOT_ADMIN.get(required_right, False)
        
    # Проверяем, является ли пользователь администратором чата
    if update.effective_chat and update.effective_chat.type != 'private':
        try:
            member = await update.effective_chat.get_member(user_id)
            is_chat_admin = member.status in ['creator', 'administrator']
            if is_chat_admin:
                return AdminRights.CHAT_ADMIN.get(required_right, False)
        except Exception:
            return False
            
    return False

__all__ = ['MARIADB_CONFIG', 'BOT_ADMIN_IDS', 'AdminRights', 'check_admin_rights'] 