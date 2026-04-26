"""Coach modul DB operatsiyalari."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from coach.models import (
    STATUS_DONE,
    STATUS_MISSED,
    STATUS_PENDING,
    STATUS_SKIPPED,
    DayStreak,
    PlanTask,
)


async def add_task(
    session: AsyncSession,
    plan_date: date,
    time_str: str,
    description: str,
) -> PlanTask:
    task = PlanTask(
        plan_date=plan_date,
        time_str=time_str,
        description=description,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def get_tasks_for_date(
    session: AsyncSession,
    plan_date: date,
) -> list[PlanTask]:
    result = await session.execute(
        select(PlanTask)
        .where(PlanTask.plan_date == plan_date)
        .order_by(PlanTask.time_str)
    )
    return list(result.scalars().all())


async def get_pending_tasks(
    session: AsyncSession,
    plan_date: date,
) -> list[PlanTask]:
    result = await session.execute(
        select(PlanTask)
        .where(PlanTask.plan_date == plan_date, PlanTask.status == STATUS_PENDING)
        .order_by(PlanTask.time_str)
    )
    return list(result.scalars().all())


async def get_current_task(
    session: AsyncSession,
    plan_date: date,
) -> PlanTask | None:
    """Hozirgi vaqtga eng yaqin pending task."""
    now_str = datetime.now().strftime("%H:%M")
    result = await session.execute(
        select(PlanTask)
        .where(
            PlanTask.plan_date == plan_date,
            PlanTask.status == STATUS_PENDING,
            PlanTask.time_str <= now_str,
        )
        .order_by(PlanTask.time_str.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def mark_task_done(session: AsyncSession, task_id: int) -> PlanTask | None:
    result = await session.execute(select(PlanTask).where(PlanTask.id == task_id))
    task = result.scalar_one_or_none()
    if task:
        task.status = STATUS_DONE
        await session.commit()
    return task


async def mark_task_skipped(
    session: AsyncSession, task_id: int, reason: str | None = None
) -> PlanTask | None:
    result = await session.execute(select(PlanTask).where(PlanTask.id == task_id))
    task = result.scalar_one_or_none()
    if task:
        task.status = STATUS_SKIPPED
        task.skip_reason = reason
        await session.commit()
    return task


async def mark_task_reminded(session: AsyncSession, task_id: int) -> None:
    await session.execute(
        update(PlanTask).where(PlanTask.id == task_id).values(reminded=True)
    )
    await session.commit()


async def increment_nudge(session: AsyncSession, task_id: int) -> int:
    result = await session.execute(select(PlanTask).where(PlanTask.id == task_id))
    task = result.scalar_one_or_none()
    if task:
        task.nudge_count += 1
        await session.commit()
        return task.nudge_count
    return 0


async def mark_overdue_as_missed(session: AsyncSession, plan_date: date) -> int:
    """Kechki 23:59 da bajarilmagan tasklarni missed qilish."""
    result = await session.execute(
        update(PlanTask)
        .where(PlanTask.plan_date == plan_date, PlanTask.status == STATUS_PENDING)
        .values(status=STATUS_MISSED)
    )
    await session.commit()
    return result.rowcount  # type: ignore[return-value]


async def clear_day_tasks(session: AsyncSession, plan_date: date) -> int:
    """Kunlik rejani tozalash."""
    tasks = await get_tasks_for_date(session, plan_date)
    count = len(tasks)
    for t in tasks:
        await session.delete(t)
    await session.commit()
    return count


# ---- Streak ----

async def record_day_result(session: AsyncSession, streak_date: date) -> bool:
    """Kunlik natijani qayd etish — barchasi bajarilganmi."""
    tasks = await get_tasks_for_date(session, streak_date)
    if not tasks:
        return False
    all_done = all(t.status == STATUS_DONE for t in tasks)
    existing = await session.execute(
        select(DayStreak).where(DayStreak.streak_date == streak_date)
    )
    row = existing.scalar_one_or_none()
    if row:
        row.all_done = all_done
    else:
        session.add(DayStreak(streak_date=streak_date, all_done=all_done))
    await session.commit()
    return all_done


async def get_current_streak(session: AsyncSession) -> int:
    """Hozirgi ketma-ket streak kunlar soni."""
    today = date.today()
    streak = 0
    check_date = today - timedelta(days=1)  # kechadan boshlab

    # Bugun ham hisoblash — agar bugun ham all_done bo'lsa
    today_result = await session.execute(
        select(DayStreak).where(DayStreak.streak_date == today)
    )
    today_row = today_result.scalar_one_or_none()
    if today_row and today_row.all_done:
        streak += 1

    while True:
        result = await session.execute(
            select(DayStreak).where(DayStreak.streak_date == check_date)
        )
        row = result.scalar_one_or_none()
        if row and row.all_done:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break
    return streak


async def get_previous_streak(session: AsyncSession) -> int:
    """Oldingi streak (buzilishdan oldingi)."""
    today = date.today()
    check_date = today - timedelta(days=1)

    # Avval buzilgan kunni topamiz
    while True:
        result = await session.execute(
            select(DayStreak).where(DayStreak.streak_date == check_date)
        )
        row = result.scalar_one_or_none()
        if row and row.all_done:
            check_date -= timedelta(days=1)
        else:
            break

    # Endi undan oldingi streak ni hisoblaymiz
    check_date -= timedelta(days=1)
    prev_streak = 0
    while True:
        result = await session.execute(
            select(DayStreak).where(DayStreak.streak_date == check_date)
        )
        row = result.scalar_one_or_none()
        if row and row.all_done:
            prev_streak += 1
            check_date -= timedelta(days=1)
        else:
            break
    return prev_streak


async def get_week_stats(
    session: AsyncSession,
    week_start: date,
    week_end: date,
) -> dict[str, int | str]:
    """Haftalik statistika."""
    result = await session.execute(
        select(PlanTask).where(
            PlanTask.plan_date >= week_start,
            PlanTask.plan_date <= week_end,
        )
    )
    tasks = list(result.scalars().all())
    total = len(tasks)
    done_count = sum(1 for t in tasks if t.status == STATUS_DONE)
    skipped_count = sum(1 for t in tasks if t.status in (STATUS_SKIPPED, STATUS_MISSED))

    # Kun bo'yicha tahlil
    day_done: dict[str, int] = {}
    day_total: dict[str, int] = {}
    day_names = [
        "Dushanba", "Seshanba", "Chorshanba", "Payshanba",
        "Juma", "Shanba", "Yakshanba",
    ]
    for t in tasks:
        day_name = day_names[t.plan_date.weekday()]
        day_done.setdefault(day_name, 0)
        day_total.setdefault(day_name, 0)
        day_total[day_name] += 1
        if t.status == STATUS_DONE:
            day_done[day_name] += 1

    best_day = ""
    worst_day = ""
    best_pct = -1.0
    worst_pct = 101.0
    for day_name in day_names:
        if day_name not in day_total or day_total[day_name] == 0:
            continue
        pct = day_done.get(day_name, 0) / day_total[day_name]
        if pct > best_pct:
            best_pct = pct
            best_day = day_name
        if pct < worst_pct:
            worst_pct = pct
            worst_day = day_name

    return {
        "total": total,
        "done": done_count,
        "skipped": skipped_count,
        "best_day": best_day,
        "worst_day": worst_day,
    }
