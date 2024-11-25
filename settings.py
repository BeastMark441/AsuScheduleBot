from pydantic import Field, MariaDBDsn
from pydantic_settings import BaseSettings

class DatabaseSettings(BaseSettings):
    DATABASE_URL: MariaDBDsn = Field(default=...)
    
class TelegramSettings(BaseSettings):
    BOT_TOKEN: str = Field(default=...)
    DEVELOPER_CHAT_ID: int | None = None
    
class AsuSettings(BaseSettings):
    ASU_TOKEN: str = Field(default=...)
    
class Settings(DatabaseSettings, TelegramSettings, AsuSettings):
    pass