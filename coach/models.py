"""Coach modul SQLite modellari — reja, check-in, streak."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from db.models import Base

# Task holatlari
STATUS_PENDING = "pending"
STATUS_DONE = "done"
STATUS_SKIPPED = "skipped"
STATUS_MISSED = "missed"


class PlanTask(Base):
    """Kunlik reja — har bir task alohida qator."""

    __tablename__ = "coach_plan_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    time_str: Mapped[str] = mapped_column(String(5), nullable=False)  # "09:00"
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=STATUS_PENDING)
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    nudge_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DayStreak(Base):
    """Kunlik streak hisobi."""

    __tablename__ = "coach_streaks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    streak_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    all_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
