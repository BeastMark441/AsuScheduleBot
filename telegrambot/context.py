from typing import Any

from telegram.ext import CallbackContext, ContextTypes, ExtBot

from database.models import Group, Lecturer
from settings import Settings

class BotData:
    _settings: Settings = None # pyright: ignore[reportAssignmentType]
    
class UserData(dict[Any, Any]):
    selected_schedule: Group | Lecturer | None = None
    
    def clear(self) -> None: # pyright: ignore[reportImplicitOverride]
        self.selected_schedule = None
        return super().clear()
    
class ApplicationContext(CallbackContext[ExtBot[None], UserData, dict[Any, Any], BotData]):
    @property
    def settings(self) -> Settings:
        return self.bot_data._settings # pyright: ignore[reportPrivateUsage]

    
context_types = ContextTypes(context=ApplicationContext, bot_data=BotData, user_data=UserData)