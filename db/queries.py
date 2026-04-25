"""Watcher mahalliy DB so'rovlari."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Anime, AutoReply, ChannelRule, ForwardedFile

# ---------- ChannelRule ----------


async def add_rule(
    session: AsyncSession,
    *,
    channel_id: int,
    pattern: str,
    pattern_type: str,
    anime_id: int,
    start_episode: int = 1,
    created_by: int,
) -> ChannelRule:
    row = ChannelRule(
        channel_id=channel_id,
        pattern=pattern,
        pattern_type=pattern_type,
        anime_id=anime_id,
        start_episode=start_episode,
        created_by=created_by,
    )
    session.add(row)
    await session.flush()
    return row


async def remove_rule(session: AsyncSession, *, rule_id: int) -> int:
    result = await session.execute(delete(ChannelRule).where(ChannelRule.id == rule_id))
    return result.rowcount or 0


async def remove_rules_for_channel(session: AsyncSession, *, channel_id: int) -> int:
    result = await session.execute(delete(ChannelRule).where(ChannelRule.channel_id == channel_id))
    return result.rowcount or 0


async def get_rules_for_channel(session: AsyncSession, channel_id: int) -> list[ChannelRule]:
    result = await session.scalars(
        select(ChannelRule).where(ChannelRule.channel_id == channel_id).order_by(ChannelRule.id)
    )
    return list(result.all())


async def list_all_rules(session: AsyncSession) -> list[ChannelRule]:
    result = await session.scalars(select(ChannelRule).order_by(ChannelRule.channel_id, ChannelRule.id))
    return list(result.all())


async def get_rule(session: AsyncSession, rule_id: int) -> ChannelRule | None:
    return await session.get(ChannelRule, rule_id)


async def list_channel_ids(session: AsyncSession) -> list[int]:
    result = await session.scalars(select(ChannelRule.channel_id).distinct())
    return list(result.all())


# ---------- AutoReply ----------


async def add_auto_reply(
    session: AsyncSession,
    *,
    pattern: str,
    pattern_type: str,
    reply_text: str,
    created_by: int,
) -> AutoReply:
    row = AutoReply(
        pattern=pattern,
        pattern_type=pattern_type,
        reply_text=reply_text,
        created_by=created_by,
        active=True,
    )
    session.add(row)
    await session.flush()
    return row


async def remove_auto_reply(session: AsyncSession, *, reply_id: int) -> int:
    result = await session.execute(delete(AutoReply).where(AutoReply.id == reply_id))
    return result.rowcount or 0


async def toggle_auto_reply(session: AsyncSession, *, reply_id: int) -> AutoReply | None:
    row = await session.get(AutoReply, reply_id)
    if row is None:
        return None
    row.active = not row.active
    await session.flush()
    return row


async def list_auto_replies(session: AsyncSession) -> list[AutoReply]:
    result = await session.scalars(select(AutoReply).order_by(AutoReply.id))
    return list(result.all())


async def list_active_auto_replies(session: AsyncSession) -> list[AutoReply]:
    result = await session.scalars(select(AutoReply).where(AutoReply.active.is_(True)).order_by(AutoReply.id))
    return list(result.all())


async def get_auto_reply(session: AsyncSession, reply_id: int) -> AutoReply | None:
    return await session.get(AutoReply, reply_id)


# ---------- ForwardedFile ----------


async def is_forwarded(session: AsyncSession, file_unique_id: str) -> bool:
    result = await session.scalar(
        select(ForwardedFile.id).where(ForwardedFile.file_unique_id == file_unique_id)
    )
    return result is not None


async def mark_forwarded(
    session: AsyncSession,
    *,
    file_unique_id: str,
    anime_id: int,
    episode: int,
    source_channel_id: int | None,
) -> None:
    existing = await session.scalar(
        select(ForwardedFile).where(ForwardedFile.file_unique_id == file_unique_id)
    )
    if existing is not None:
        return
    row = ForwardedFile(
        file_unique_id=file_unique_id,
        anime_id=anime_id,
        episode=episode,
        source_channel_id=source_channel_id,
    )
    session.add(row)
    await session.flush()


async def recent_forwarded(session: AsyncSession, limit: int = 10) -> list[ForwardedFile]:
    result = await session.scalars(select(ForwardedFile).order_by(ForwardedFile.id.desc()).limit(limit))
    return list(result.all())


# ---------- Anime ----------


async def find_anime_by_normalized_name(
    session: AsyncSession, name_normalized: str, season: int | None = None
) -> Anime | None:
    stmt = select(Anime).where(Anime.name_normalized == name_normalized)
    if season is not None:
        stmt = stmt.where(Anime.season == season)
    else:
        stmt = stmt.where(Anime.season.is_(None))
    result = await session.scalar(stmt)
    if result is not None:
        return result
    if season is not None:
        fallback = await session.scalar(
            select(Anime).where(Anime.name_normalized == name_normalized, Anime.season.is_(None))
        )
        return fallback
    return None


async def find_anime_by_normalized_name_any(
    session: AsyncSession, name_normalized: str
) -> Anime | None:
    result = await session.scalar(
        select(Anime).where(Anime.name_normalized == name_normalized).limit(1)
    )
    return result


async def create_anime(
    session: AsyncSession,
    *,
    name: str,
    name_normalized: str,
    season: int | None,
    created_by: int,
) -> Anime:
    row = Anime(
        name=name,
        name_normalized=name_normalized,
        season=season,
        created_by=created_by,
    )
    session.add(row)
    await session.flush()
    return row


async def list_all_anime(session: AsyncSession) -> list[Anime]:
    result = await session.scalars(select(Anime).order_by(Anime.id))
    return list(result.all())


async def get_anime(session: AsyncSession, anime_id: int) -> Anime | None:
    return await session.get(Anime, anime_id)


async def remove_anime(session: AsyncSession, *, anime_id: int) -> int:
    result = await session.execute(delete(Anime).where(Anime.id == anime_id))
    return result.rowcount or 0


async def get_max_episode_for_anime(session: AsyncSession, anime_id: int) -> int:
    result = await session.scalar(
        select(func.max(ForwardedFile.episode)).where(ForwardedFile.anime_id == anime_id)
    )
    return result or 0
