"""APScheduler bilan smart eslatma tizimi.

Har daqiqa tekshiradi:
- 5 daqiqa oldin → ogohlantirish
- Vaqti kelganda → "boshlandi"
- 15 daqiqa o'tsa → nudge
- 30 daqiqa o'tsa → qattiq nudge
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telethon import TelegramClient

from coach.models import STATUS_PENDING
from coach.motivation import random_nudge
from coach.queries import (
    get_current_streak,
    get_previous_streak,
    get_tasks_for_date,
    get_week_stats,
    increment_nudge,
    mark_overdue_as_missed,
    mark_task_reminded,
    record_day_result,
)
from coach.reports import format_weekly_report
from config import settings
from db.engine import AsyncSessionLocal

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_client: TelegramClient | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    return _scheduler


def set_coach_client(client: TelegramClient) -> None:
    global _client
    _client = client


async def _send_to_owner(text: str) -> None:
    if _client is None:
        log.warning("Coach client o'rnatilmagan — xabar yuborilmadi")
        return
    try:
        await _client.send_message(settings.OWNER_ID, text)
    except Exception:
        log.exception("Owner ga xabar yuborishda xato")


async def _check_reminders() -> None:
    """Har daqiqada chaqiriladi — tasklarga eslatma."""
    now = datetime.now()
    today = date.today()
    now_time = now.time()

    async with AsyncSessionLocal() as session:
        tasks = await get_tasks_for_date(session, today)

        for task in tasks:
            if task.status != STATUS_PENDING:
                continue

            # Task vaqtini parse qilish
            try:
                parts = task.time_str.split(":")
                task_time = time(int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                continue

            task_dt = datetime.combine(today, task_time)
            diff_minutes = (now - task_dt).total_seconds() / 60

            # 5 daqiqa oldin
            pre_dt = task_dt - timedelta(minutes=5)
            pre_diff = abs((now - pre_dt).total_seconds())
            if pre_diff < 45 and not task.reminded:
                await _send_to_owner(
                    f"{task.time_str} — {task.description} vaqti. Tayyor bo'l."
                )
                await mark_task_reminded(session, task.id)
                continue

            # Vaqti kelganda (0-2 daqiqa)
            if 0 <= diff_minutes <= 2 and task.reminded and task.nudge_count == 0:
                await _send_to_owner(
                    f"{task.description} boshlandi. Bajarasan."
                )
                await increment_nudge(session, task.id)
                continue

            # 15 daqiqa o'tsa
            if 14 <= diff_minutes <= 16 and task.nudge_count == 1:
                await _send_to_owner(
                    f"Hali qilmadingmi? Tur. ({task.time_str} — {task.description})"
                )
                await increment_nudge(session, task.id)
                continue

            # 30 daqiqa o'tsa
            if 29 <= diff_minutes <= 31 and task.nudge_count == 2:
                await _send_to_owner(
                    f"Qildingmi yoki yo'qmi? Javob ber. ({task.time_str} — {task.description})\n\n"
                    f'{random_nudge()}'
                )
                await increment_nudge(session, task.id)
                continue

            # 60+ daqiqa — har 30 daqiqada nudge
            if diff_minutes >= 60 and task.nudge_count >= 3:
                # Har 30 daqiqada
                since_last = diff_minutes - (task.nudge_count - 2) * 30
                if 0 <= since_last <= 2:
                    await _send_to_owner(random_nudge())
                    await increment_nudge(session, task.id)


async def _end_of_day() -> None:
    """Kun oxirida — bajarilmagan tasklarni missed qilish + streak hisoblash."""
    today = date.today()

    async with AsyncSessionLocal() as session:
        missed = await mark_overdue_as_missed(session, today)
        if missed > 0:
            await _send_to_owner(
                f"Bugun {missed} ta task bajarilmadi va o'tkazildi."
            )

        all_done = await record_day_result(session, today)
        streak = await get_current_streak(session)

        if all_done:
            await _send_to_owner(
                f"Bugun barcha rejani bajardingiz! Streak: {streak} kun"
            )
        else:
            prev_streak = await get_previous_streak(session)
            if prev_streak > 0:
                await _send_to_owner(
                    f"{prev_streak} kunlik streak ketdi. Ertaga qaytadan boshla."
                )


async def _weekly_report() -> None:
    """Har yakshanba kechqurun — haftalik hisobot."""
    today = date.today()
    # Hafta boshi (Dushanba)
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    async with AsyncSessionLocal() as session:
        stats = await get_week_stats(session, week_start, week_end)
        streak = await get_current_streak(session)
        report = format_weekly_report(stats, streak)
        await _send_to_owner(report)


def start_scheduler(client: TelegramClient) -> None:
    """Schedulerni ishga tushirish."""
    set_coach_client(client)
    scheduler = get_scheduler()

    # Har daqiqada reminder tekshirish
    scheduler.add_job(
        _check_reminders,
        "interval",
        minutes=1,
        id="coach_reminders",
        replace_existing=True,
    )

    # Kun oxirida (23:55) — streak hisoblash
    scheduler.add_job(
        _end_of_day,
        "cron",
        hour=23,
        minute=55,
        timezone="Asia/Tashkent",
        id="coach_end_of_day",
        replace_existing=True,
    )

    # Har yakshanba 21:00 — haftalik hisobot
    scheduler.add_job(
        _weekly_report,
        "cron",
        day_of_week="sun",
        hour=21,
        minute=0,
        timezone="Asia/Tashkent",
        id="coach_weekly_report",
        replace_existing=True,
    )

    scheduler.start()
    log.info("Coach scheduler ishga tushdi")
