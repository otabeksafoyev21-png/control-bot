"""Userbot event handlers.

Yangi xabar kelganda:
1. Agar xabar **shaxsiy chat**da (kontakt) bo'lsa — avtojavob qoidalari
   tekshiriladi (1-2 daqiqa kechikish bilan — odamday).
2. Aks holda (kanal xabari):
   a. Avval `watcher_channel_rules` ichida mos qoida qidiriladi.
   b. Agar qoida topilmasa — caption dan anime nomi ajratiladi va
      kaworai PostgreSQL dan case-insensitive qidiruv qilinadi.
      Kaworai DB yo'q bo'lsa — mahalliy `watcher_anime` jadvalidan qidiriladi.
3. Mos anime topilsa: watcher videoni kaworai SECRET_CHANNEL ga
   "ID: <anime_id>\\nQism: <episode>" caption bilan post qiladi.
   Kaworai_bot o'zining `add_episode_from_channel` handleri bilan DB-ga yozadi.
"""

from __future__ import annotations

import asyncio
import logging
import random

from telethon import TelegramClient, events
from telethon.tl.types import (
    DocumentAttributeFilename,
    DocumentAttributeVideo,
    MessageMediaDocument,
    PeerUser,
    User,
)

from config import settings
from db.engine import AsyncSessionLocal
from db.kaworai import lookup_anime_by_name
from db.queries import (
    find_anime_by_normalized_name,
    get_max_episode_for_anime,
    get_rules_for_channel,
    is_forwarded,
    list_active_auto_replies,
    list_channel_ids,
    mark_forwarded,
)
from userbot.matcher import normalize_name, parse_meta
from userbot.rules import match_pattern

log = logging.getLogger(__name__)


def _extract_video_meta(message: object) -> tuple[str | None, int, str | None]:
    """Return (file_unique_id, duration, filename) yoki (None, 0, None)."""
    media = getattr(message, "media", None)
    if not isinstance(media, MessageMediaDocument) or media.document is None:
        return None, 0, None
    doc = media.document
    is_video = False
    duration = 0
    filename: str | None = None
    for attr in getattr(doc, "attributes", []) or []:
        if isinstance(attr, DocumentAttributeVideo):
            is_video = True
            duration = int(getattr(attr, "duration", 0) or 0)
        elif isinstance(attr, DocumentAttributeFilename):
            filename = attr.file_name
    if not is_video and not (doc.mime_type or "").startswith("video/"):
        return None, 0, None
    file = getattr(message, "file", None)
    unique_id: str | None = getattr(file, "unique_id", None) if file else None
    return unique_id, duration, filename


async def _handle_channel_message(event: events.NewMessage.Event) -> None:
    message = event.message
    peer_id = getattr(event.chat, "id", None)
    if peer_id is None:
        return

    candidates = [peer_id]
    if peer_id > 0:
        candidates.append(int(f"-100{peer_id}"))
    if peer_id < 0:
        raw = str(peer_id).lstrip("-")
        if raw.startswith("100"):
            candidates.append(int(raw[3:]))

    async with AsyncSessionLocal() as session:
        rules: list = []
        matched_channel_id = peer_id
        for cid in candidates:
            rules = await get_rules_for_channel(session, cid)
            if rules:
                matched_channel_id = cid
                break

        if not rules:
            known_channels = await list_channel_ids(session)
            is_known = any(cid in known_channels for cid in candidates)
            if not is_known:
                return

        unique_id, duration, filename = _extract_video_meta(message)
        if unique_id is None:
            return
        if duration and duration < settings.MIN_VIDEO_DURATION:
            log.info("Skip (qisqa video duration=%ss) uid=%s", duration, unique_id)
            return
        if await is_forwarded(session, unique_id):
            log.info("Skip (allaqachon yuborilgan) uid=%s", unique_id)
            return

        caption_text = message.message or ""
        meta = parse_meta(caption_text or filename or "")
        anime_id: int | None = None
        episode: int | None = meta.episode
        start_episode: int = 1

        # 1-usul: Qoidalar bilan moslashtirish
        if rules:
            for rule in rules:
                if match_pattern(caption_text, rule.pattern, rule.pattern_type):
                    anime_id = rule.anime_id
                    start_episode = rule.start_episode
                    break

        # 2-usul: Anime nomi bilan auto-detect (kaworai DB -> mahalliy DB)
        if anime_id is None and meta.title:
            norm = normalize_name(meta.title)
            if norm:
                # Avval kaworai PostgreSQL dan qidirish
                kaworai_result = await lookup_anime_by_name(norm, meta.season)
                if kaworai_result is not None:
                    anime_id = kaworai_result[0]
                    log.info(
                        "Kaworai DB: '%s' -> anime #%s '%s'",
                        meta.title, anime_id, kaworai_result[1],
                    )
                else:
                    # Mahalliy SQLite dan qidirish (fallback)
                    local_anime = await find_anime_by_normalized_name(
                        session, norm, meta.season,
                    )
                    if local_anime is not None:
                        anime_id = local_anime.id
                        log.info(
                            "Local DB: '%s' -> anime #%s", meta.title, anime_id,
                        )

        if anime_id is None:
            log.info(
                "Skip (anime aniqlanmadi) channel=%s uid=%s caption=%r",
                matched_channel_id, unique_id, caption_text[:80],
            )
            return

        # Qism raqamini aniqlash
        if episode is None:
            max_ep = await get_max_episode_for_anime(session, anime_id)
            episode = max_ep + 1
            log.info("Episode auto-increment: anime=%s -> ep=%s", anime_id, episode)

        # start_episode tekshirish — bundan oldingi qismlarni o'tkazib yuborish
        if episode < start_episode:
            log.info(
                "Skip (ep=%s < start_episode=%s) anime=%s uid=%s",
                episode, start_episode, anime_id, unique_id,
            )
            return

    caption_out = f"ID: {anime_id}\nQism: {episode}"
    try:
        await event.client.send_file(
            settings.SECRET_CHANNEL_ID,
            file=message.media,
            caption=caption_out,
        )
    except Exception:
        log.exception(
            "SECRET_CHANNEL ga yuborishda xato (anime=%s ep=%s uid=%s)",
            anime_id, episode, unique_id,
        )
        return

    async with AsyncSessionLocal() as session:
        await mark_forwarded(
            session,
            file_unique_id=unique_id,
            anime_id=anime_id,
            episode=episode,
            source_channel_id=matched_channel_id,
        )
        await session.commit()

    log.info(
        "SECRET_CHANNEL ga yuborildi: anime=%s ep=%s uid=%s channel=%s",
        anime_id, episode, unique_id, matched_channel_id,
    )


async def _handle_private_message(event: events.NewMessage.Event) -> None:
    """Kontaktdan kelgan shaxsiy xabarga avtojavob (kechikish bilan)."""
    sender = await event.get_sender()
    if not isinstance(sender, User):
        return
    if sender.bot or sender.is_self:
        return
    if not getattr(sender, "contact", False):
        return

    text = event.message.message or ""
    if not text:
        return

    async with AsyncSessionLocal() as session:
        replies = await list_active_auto_replies(session)

    for reply in replies:
        if match_pattern(text, reply.pattern, reply.pattern_type):
            # Odamday kechikish — 1-2 daqiqa (max 5 daqiqa)
            min_delay = settings.AUTO_REPLY_MIN_DELAY
            max_delay = settings.AUTO_REPLY_MAX_DELAY
            delay = random.randint(min_delay, max_delay)
            log.info(
                "Avtojavob %d soniya kutadi (sender=%s)", delay, sender.id,
            )
            await asyncio.sleep(delay)
            try:
                await event.client.send_message(sender.id, reply.reply_text)
            except Exception:
                log.exception("Avtojavob yuborishda xato (sender=%s)", sender.id)
            return


async def _dispatch(event: events.NewMessage.Event) -> None:
    if isinstance(event.message.peer_id, PeerUser):
        await _handle_private_message(event)
        return
    await _handle_channel_message(event)


def register(client: TelegramClient) -> None:
    """Telethon handlerlarni ro'yxatdan o'tkazish."""

    @client.on(events.NewMessage(incoming=True))
    async def _on_new_message(event: events.NewMessage.Event) -> None:
        try:
            await _dispatch(event)
        except Exception:
            log.exception("Userbot xabarni qayta ishlashda xato")
