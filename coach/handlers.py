"""Coach komandalar — Telethon userbot orqali.

Komandalar:
/plan HH:MM Tavsif     — reja qo'shish
/today                  — bugungi reja
/done                   — joriy taskni bajarildi deb belgilash
/skip                   — joriy taskni o'tkazish
/streak                 — streak ko'rsatish
/clear                  — bugungi rejani tozalash
/week                   — haftalik hisobot

Shuningdek "qildim" va "qilmadim" matnlari ham ishlaydi.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta

from telethon import TelegramClient, events

from coach.models import STATUS_DONE, STATUS_PENDING, STATUS_SKIPPED
from coach.motivation import (
    random_done,
    random_nudge,
    random_skip_ack,
    random_skip_ask,
    streak_broken_msg,
)
from coach.queries import (
    add_task,
    clear_day_tasks,
    get_current_streak,
    get_current_task,
    get_pending_tasks,
    get_previous_streak,
    get_tasks_for_date,
    get_week_stats,
    mark_task_done,
    mark_task_skipped,
    record_day_result,
)
from coach.reports import format_weekly_report
from config import settings
from db.engine import AsyncSessionLocal

log = logging.getLogger(__name__)

# Holat — skip sababi kutilmoqdami
_waiting_skip_reason: dict[int, int] = {}  # owner_id -> task_id


def _is_owner(event: events.NewMessage.Event) -> bool:
    sender_id = event.sender_id
    return sender_id == settings.OWNER_ID


def _format_task_line(task: object) -> str:
    """Task ni chiroyli formatlash."""
    status_icon = {
        STATUS_PENDING: "",
        STATUS_DONE: "[bajarildi]",
        STATUS_SKIPPED: "[o'tkazildi]",
        "missed": "[o'tkazildi]",
    }
    icon = status_icon.get(task.status, "")  # type: ignore[union-attr]
    return f"{task.time_str} — {task.description} {icon}".strip()  # type: ignore[union-attr]


def register_coach_handlers(client: TelegramClient) -> None:
    """Coach komandalarini ro'yxatga olish."""

    @client.on(events.NewMessage(outgoing=True, pattern=r"^/plan\s+"))
    async def on_plan(event: events.NewMessage.Event) -> None:
        """Reja qo'shish: /plan 09:00 Mashq"""
        text = event.raw_text.strip()
        match = re.match(r"^/plan\s+(\d{1,2}:\d{2})\s+(.+)$", text, re.DOTALL)
        if not match:
            await event.reply(
                "Format: /plan HH:MM Tavsif\n"
                "Masalan: /plan 09:00 Mashq (30 daqiqa)"
            )
            return

        time_str = match.group(1)
        description = match.group(2).strip()

        # Vaqtni tekshirish
        try:
            parts = time_str.split(":")
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
            time_str = f"{h:02d}:{m:02d}"
        except (ValueError, IndexError):
            await event.reply("Vaqt noto'g'ri. Format: HH:MM (masalan 09:00)")
            return

        today = date.today()
        async with AsyncSessionLocal() as session:
            task = await add_task(session, today, time_str, description)
            tasks = await get_tasks_for_date(session, today)
            count = len(tasks)

        await event.reply(
            f"Qo'shildi: {time_str} — {description}\n"
            f"Bugun {count} ta task bor."
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^/today$"))
    async def on_today(event: events.NewMessage.Event) -> None:
        """Bugungi rejani ko'rsatish."""
        today = date.today()
        async with AsyncSessionLocal() as session:
            tasks = await get_tasks_for_date(session, today)

        if not tasks:
            await event.reply("Bugun reja yo'q. /plan bilan qo'sh.")
            return

        lines = ["Bugungi reja:\n"]
        for i, t in enumerate(tasks, 1):
            lines.append(f"{i}. {_format_task_line(t)}")

        pending = sum(1 for t in tasks if t.status == STATUS_PENDING)
        done = sum(1 for t in tasks if t.status == STATUS_DONE)
        lines.append(f"\nBajarildi: {done}/{len(tasks)} | Kutmoqda: {pending}")
        await event.reply("\n".join(lines))

    @client.on(events.NewMessage(outgoing=True, pattern=r"^/done(\s+\d+)?$"))
    async def on_done(event: events.NewMessage.Event) -> None:
        """Taskni bajarildi deb belgilash."""
        today = date.today()
        async with AsyncSessionLocal() as session:
            # /done 3 — 3-task ni bajarish
            match = re.match(r"^/done\s+(\d+)$", event.raw_text.strip())
            if match:
                task_num = int(match.group(1))
                tasks = await get_tasks_for_date(session, today)
                if 1 <= task_num <= len(tasks):
                    task = tasks[task_num - 1]
                else:
                    await event.reply(f"Task #{task_num} topilmadi.")
                    return
            else:
                # Joriy pending taskni olish
                task = await get_current_task(session, today)
                if not task:
                    pending = await get_pending_tasks(session, today)
                    if pending:
                        task = pending[0]
                    else:
                        await event.reply("Bajarilmagan task yo'q!")
                        return

            await mark_task_done(session, task.id)

            # Keyingi pending task bormi?
            remaining = await get_pending_tasks(session, today)
            reply = random_done()
            if remaining:
                next_t = remaining[0]
                reply += f" Keyingisi {next_t.time_str} — {next_t.description}"
            else:
                # Barchasi bajarildi!
                await record_day_result(session, today)
                streak = await get_current_streak(session)
                reply += f"\n\nBugungi barcha reja bajarildi! Streak: {streak} kun"

        await event.reply(reply)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^/skip(\s+\d+)?$"))
    async def on_skip(event: events.NewMessage.Event) -> None:
        """Taskni o'tkazish."""
        today = date.today()
        async with AsyncSessionLocal() as session:
            match = re.match(r"^/skip\s+(\d+)$", event.raw_text.strip())
            if match:
                task_num = int(match.group(1))
                tasks = await get_tasks_for_date(session, today)
                if 1 <= task_num <= len(tasks):
                    task = tasks[task_num - 1]
                else:
                    await event.reply(f"Task #{task_num} topilmadi.")
                    return
            else:
                task = await get_current_task(session, today)
                if not task:
                    pending = await get_pending_tasks(session, today)
                    if pending:
                        task = pending[0]
                    else:
                        await event.reply("O'tkazadigan task yo'q!")
                        return

            # Sabab so'rash
            _waiting_skip_reason[settings.OWNER_ID] = task.id
            await event.reply(random_skip_ask())

    @client.on(events.NewMessage(outgoing=True, pattern=r"^/streak$"))
    async def on_streak(event: events.NewMessage.Event) -> None:
        """Streak ko'rsatish."""
        async with AsyncSessionLocal() as session:
            streak = await get_current_streak(session)

        if streak == 0:
            await event.reply("Hozir streak yo'q. Bugundan boshla!")
        else:
            await event.reply(f"Streak: {streak} kun davom etmoqda!")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^/clear$"))
    async def on_clear(event: events.NewMessage.Event) -> None:
        """Bugungi rejani tozalash."""
        today = date.today()
        async with AsyncSessionLocal() as session:
            count = await clear_day_tasks(session, today)
        await event.reply(f"Bugungi {count} ta task tozalandi.")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^/week$"))
    async def on_week(event: events.NewMessage.Event) -> None:
        """Haftalik hisobot."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        async with AsyncSessionLocal() as session:
            stats = await get_week_stats(session, week_start, week_end)
            streak = await get_current_streak(session)

        report = format_weekly_report(stats, streak)
        await event.reply(report)

    @client.on(events.NewMessage(outgoing=True))
    async def on_text_checkin(event: events.NewMessage.Event) -> None:
        """Matnli check-in: 'qildim' yoki 'qilmadim'."""
        if not event.raw_text:
            return
        text = event.raw_text.strip().lower()

        # Komandalarni e'tiborsiz qoldirish
        if text.startswith("/"):
            return

        # Skip sababi kutilmoqda
        if settings.OWNER_ID in _waiting_skip_reason:
            task_id = _waiting_skip_reason.pop(settings.OWNER_ID)
            async with AsyncSessionLocal() as session:
                await mark_task_skipped(session, task_id, reason=text)
            await event.reply(random_skip_ack())
            return

        # "qildim" → done
        if text in ("qildim", "bajarildi", "tayyor", "done", "ha"):
            today = date.today()
            async with AsyncSessionLocal() as session:
                task = await get_current_task(session, today)
                if not task:
                    pending = await get_pending_tasks(session, today)
                    if pending:
                        task = pending[0]
                if not task:
                    return  # hech narsa qilmaymiz
                await mark_task_done(session, task.id)
                remaining = await get_pending_tasks(session, today)
                reply = random_done()
                if remaining:
                    next_t = remaining[0]
                    reply += f" Keyingisi {next_t.time_str} — {next_t.description}"
                else:
                    await record_day_result(session, today)
                    streak = await get_current_streak(session)
                    reply += f"\n\nBugungi barcha reja bajarildi! Streak: {streak} kun"
            await event.reply(reply)
            return

        # "qilmadim" → skip
        if text in ("qilmadim", "yo'q", "skip"):
            today = date.today()
            async with AsyncSessionLocal() as session:
                task = await get_current_task(session, today)
                if not task:
                    pending = await get_pending_tasks(session, today)
                    if pending:
                        task = pending[0]
                if not task:
                    return
                _waiting_skip_reason[settings.OWNER_ID] = task.id
            await event.reply(random_skip_ask())
            return

    @client.on(events.NewMessage(outgoing=True, pattern=r"^/help_coach$"))
    async def on_help_coach(event: events.NewMessage.Event) -> None:
        """Coach yordam."""
        await event.reply(
            "Personal Coach komandalar:\n\n"
            "/plan HH:MM Tavsif — reja qo'shish\n"
            "/today — bugungi reja\n"
            "/done — joriy taskni bajarildi\n"
            "/done 3 — 3-taskni bajarildi\n"
            "/skip — joriy taskni o'tkazish\n"
            "/skip 2 — 2-taskni o'tkazish\n"
            "/streak — streak ko'rsatish\n"
            "/week — haftalik hisobot\n"
            "/clear — bugungi rejani tozalash\n\n"
            "Shuningdek 'qildim' va 'qilmadim' deb yozsangiz ham ishlaydi."
        )
