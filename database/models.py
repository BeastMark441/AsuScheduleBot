from datetime import datetime
from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import enum


class Base(AsyncAttrs, DeclarativeBase):
    pass

class SearchType(enum.Enum):
    group = 1,
    lecturer = 2,

class Stats(Base):
    __tablename__: str = "stats"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(nullable=False)
    search_type: Mapped[SearchType] = mapped_column(nullable=False)
    search_query: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    
