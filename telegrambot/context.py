from typing import Any

from telegram.ext import CallbackContext, ContextTypes, ExtBot

from settings import Settings

class BotData:
    _settings: Settings = None # pyright: ignore[reportAssignmentType]
    
class ApplicationContext(CallbackContext[ExtBot[None], dict[Any, Any], dict[Any, Any], BotData]):
    @property
    def settings(self) -> Settings:
        return self.bot_data._settings # pyright: ignore[reportPrivateUsage]
    
    
context_types = ContextTypes(context=ApplicationContext, bot_data=BotData)