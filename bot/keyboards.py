"""Inline keyboard builders for the control bot UI."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from db.models import AutoReply, ChannelRule


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="\U0001f4fa Kanallar", callback_data="menu:channels")],
            [InlineKeyboardButton(text="\U0001f4ac Avtojavoblar", callback_data="menu:replies")],
            [
                InlineKeyboardButton(text="\u2699\ufe0f Holat", callback_data="menu:status"),
                InlineKeyboardButton(text="\U0001f4dc So'nggi", callback_data="menu:forwarded"),
            ],
            [InlineKeyboardButton(text="\u2139\ufe0f Yordam", callback_data="menu:help")],
        ]
    )


def back_to_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="\u25c0\ufe0f Bosh menyu", callback_data="menu:main")]]
    )


def channels_list(channel_groups: list[tuple[int, int, str | None]]) -> InlineKeyboardMarkup:
    """channel_groups: list of (channel_id, rules_count, title_or_None)."""
    rows: list[list[InlineKeyboardButton]] = []
    for channel_id, count, title in channel_groups:
        label = title or str(channel_id)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"\U0001f4fa {label} ({count} qoida)",
                    callback_data=f"ch:view:{channel_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="\u2795 Yangi kanal qo'shish", callback_data="ch:add")])
    rows.append([InlineKeyboardButton(text="\u25c0\ufe0f Bosh menyu", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channel_detail(channel_id: int, rules: list[ChannelRule]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for rule in rules:
        preview = _pattern_label(rule.pattern, rule.pattern_type)
        ep_label = f" (ep\u2265{rule.start_episode})" if rule.start_episode > 1 else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"\U0001f5d1 #{rule.id} {preview} \u2192 anime #{rule.anime_id}{ep_label}",
                    callback_data=f"rule:delask:{rule.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="\u2795 Qoida qo'shish", callback_data=f"ch:addrule:{channel_id}")])
    rows.append([InlineKeyboardButton(text="\U0001f6aa Kanaldan chiqish", callback_data=f"ch:leave:{channel_id}")])
    rows.append([InlineKeyboardButton(text="\u25c0\ufe0f Kanallar", callback_data="menu:channels")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_delete(rule_id: int, channel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Ha, o'chir", callback_data=f"rule:delok:{rule_id}"),
                InlineKeyboardButton(text="Bekor", callback_data=f"ch:view:{channel_id}"),
            ]
        ]
    )


def confirm_leave(channel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Ha, chiqish", callback_data=f"ch:leaveok:{channel_id}"),
                InlineKeyboardButton(text="Bekor", callback_data=f"ch:view:{channel_id}"),
            ]
        ]
    )


def pattern_type_choice(context: str) -> InlineKeyboardMarkup:
    """context is free text that identifies the wizard (e.g., 'rule', 'reply')."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="\U0001f4dd Oddiy matn", callback_data=f"ptype:{context}:substring"),
                InlineKeyboardButton(text="\U0001f9e9 Regex", callback_data=f"ptype:{context}:regex"),
            ],
            [InlineKeyboardButton(text="\U0001f310 Barcha videolar", callback_data=f"ptype:{context}:all")],
            [InlineKeyboardButton(text="Bekor", callback_data="wiz:cancel")],
        ]
    )


def wizard_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Bekor", callback_data="wiz:cancel")]]
    )


def replies_list(replies: list[AutoReply]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for r in replies:
        preview = _pattern_label(r.pattern, r.pattern_type)
        state = "\U0001f7e2" if r.active else "\u26aa"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{state} #{r.id} {preview}",
                    callback_data=f"ar:view:{r.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="\u2795 Yangi avtojavob", callback_data="ar:add")])
    rows.append([InlineKeyboardButton(text="\u25c0\ufe0f Bosh menyu", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reply_detail(reply: AutoReply) -> InlineKeyboardMarkup:
    toggle_text = "\U0001f534 O'chirish" if reply.active else "\U0001f7e2 Yoqish"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=toggle_text, callback_data=f"ar:toggle:{reply.id}"),
                InlineKeyboardButton(text="\U0001f5d1 O'chir", callback_data=f"ar:delask:{reply.id}"),
            ],
            [InlineKeyboardButton(text="\u25c0\ufe0f Avtojavoblar", callback_data="menu:replies")],
        ]
    )


def confirm_delete_reply(reply_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Ha, o'chir", callback_data=f"ar:delok:{reply_id}"),
                InlineKeyboardButton(text="Bekor", callback_data=f"ar:view:{reply_id}"),
            ]
        ]
    )


def _pattern_label(pattern: str, pattern_type: str) -> str:
    if not pattern:
        return "\u00abistalgan\u00bb"
    preview = pattern[:24] + ("\u2026" if len(pattern) > 24 else "")
    tag = "re" if pattern_type == "regex" else "txt"
    return f"[{tag}] {preview}"
