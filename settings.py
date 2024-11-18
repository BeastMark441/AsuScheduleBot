from pydantic_settings import BaseSettings

class DatabaseSettings(BaseSettings):
    DATABASE_URL: str
    
class TelegramSettings(BaseSettings):
    BOT_TOKEN: str
    DEVELOPER_CHAT_ID: int | None = None
    
class AsuSettings(BaseSettings):
    ASU_TOKEN: str
    
class Settings(DatabaseSettings, TelegramSettings, AsuSettings):
    pass