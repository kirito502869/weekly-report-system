"""Database entities; stored timestamps are naive UTC (SQLite convention)."""

from datetime import UTC, date, datetime
from enum import Enum

from sqlalchemy import CheckConstraint, Date, DateTime, Enum as SAEnum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class WorkItemStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    work_items: Mapped[list["WorkItem"]] = relationship(back_populates="user")


class WorkItem(Base):
    __tablename__ = "work_items"
    __table_args__ = (
        Index("ix_work_items_user_week", "user_id", "week_start"),
        CheckConstraint("strftime('%w', week_start) = '1'", name="ck_week_start_monday"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(50))
    status: Mapped[WorkItemStatus] = mapped_column(
        SAEnum(WorkItemStatus, native_enum=False, create_constraint=True,
               validate_strings=True, name="work_item_status"),
        default=WorkItemStatus.pending,
    )
    week_start: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    user: Mapped[User] = relationship(back_populates="work_items")
