from datetime import datetime
import enum

from sqlalchemy import ForeignKey, String, Text, BigInteger, select
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_method


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Group(Base):
    __tablename__: str = "groups"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(nullable=False)
    faculty_id: Mapped[int] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    @property
    def schedule_url(self) -> str:
        return f"https://www.asu.ru/timetable/students/{self.faculty_id}/{self.group_id}/"
    
class Lecturer(Base):
    __tablename__: str = "lecturers"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    lecturer_id: Mapped[int] = mapped_column(nullable=False)
    faculty_id: Mapped[int] = mapped_column(nullable=False)
    chair_id: Mapped[int] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[str] = mapped_column(String(32), nullable=False)
    
    @property
    def schedule_url(self) -> str:
        return f"https://www.asu.ru/timetable/lecturers/{self.faculty_id}/{self.chair_id}/{self.lecturer_id}/"
    
class GroupSchedule(Base):
    __tablename__: str = "group_schedules"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    data: Mapped[str] = mapped_column(Text, nullable=True)
    expired_at: Mapped[datetime] = mapped_column(nullable=False)
    
class LecturerSchedule(Base):
    __tablename__: str = "lecturer_schedules"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("lecturers.id"), nullable=False)
    data: Mapped[str] = mapped_column(Text, nullable=True)
    expired_at: Mapped[datetime] = mapped_column(nullable=False)
    
class User(Base):
    __tablename__: str = "users"
    
    id: Mapped[int] = mapped_column(BigInteger(), primary_key=True)
    saved_group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True)
    saved_lecturer_id: Mapped[int | None] = mapped_column(ForeignKey("lecturers.id"), nullable=True)
    
    @hybrid_method
    async def saved_group(self, session: AsyncSession):
        stmt = select(Group).where(Group.id == self.saved_group_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    @hybrid_method
    async def saved_lecturer(self, session: AsyncSession):
        stmt = select(Lecturer).where(Lecturer.id == self.saved_lecturer_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
        
    
class Faculty(Base):
    __tablename__: str = "faculties"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    faculty_code: Mapped[str] = mapped_column(String(50), nullable=False)
    faculty_id: Mapped[int] = mapped_column(nullable=False)

class SearchType(enum.Enum):
    group = 1,
    lecturer = 2,

class Stat(Base):
    __tablename__: str = "stats"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(nullable=False)
    search_type: Mapped[SearchType] = mapped_column(nullable=False)
    search_query: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)