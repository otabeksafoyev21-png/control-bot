"""Haftalik hisobot formatlash."""

from __future__ import annotations


def format_weekly_report(stats: dict[str, int | str], streak: int) -> str:
    total = stats.get("total", 0)
    done = stats.get("done", 0)
    skipped = stats.get("skipped", 0)
    best_day = stats.get("best_day", "—")
    worst_day = stats.get("worst_day", "—")

    return (
        "Bu hafta:\n"
        f"Bajarildi: {done}/{total} task\n"
        f"O'tkazildi: {skipped}\n"
        f"Streak: {streak} kun\n"
        f"Eng yaxshi kun: {best_day}\n"
        f"Eng dangasa kun: {worst_day}\n\n"
        "Kelasi hafta rejangni kirit."
    )
