"""Kaworai bot PostgreSQL — faqat o'qish uchun ulanish.

Bu modul kaworai botning `animes` jadvalidan anime nomi va ID sini olish
uchun ishlatiladi. `KAWORAI_DATABASE_URL` sozlanmagan bo'lsa — hech narsa
qilmaydi (None qaytaradi).
"""

from __future__ import annotations

import logging
import re

from config import settings

log = logging.getLogger(__name__)

_kaworai_engine = None
_KaworaiSessionLocal = None

_SEASON_SUFFIX_RE = re.compile(r"\s+\d+\s*-?\s*fasl\s*$", re.IGNORECASE)


def _strip_season_suffix(title: str) -> str:
    """'Naruto 2-fasl' -> 'Naruto'."""
    return _SEASON_SUFFIX_RE.sub("", title or "").strip()


def _init_kaworai_engine() -> bool:
    """Kaworai PostgreSQL engine yaratish. True — muvaffaqiyatli."""
    global _kaworai_engine, _KaworaiSessionLocal  # noqa: PLW0603

    url = settings.KAWORAI_DATABASE_URL.strip()
    if not url:
        return False

    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    try:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        _kaworai_engine = create_async_engine(url, echo=False, pool_size=3, max_overflow=2, pool_pre_ping=True)
        _KaworaiSessionLocal = async_sessionmaker(bind=_kaworai_engine, class_=AsyncSession, expire_on_commit=False)
        log.info("Kaworai PostgreSQL ulandi")
        return True
    except Exception:
        log.exception("Kaworai PostgreSQL ulanishda xato")
        return False


async def lookup_anime_by_name(
    name_normalized: str, season: int | None = None
) -> tuple[int, str] | None:
    """Kaworai DB dan anime qidirish (case-insensitive).

    Return: (anime_id, title) yoki None.
    """
    if _KaworaiSessionLocal is None:
        if not _init_kaworai_engine():
            return None

    if _KaworaiSessionLocal is None:
        return None

    try:
        from sqlalchemy import Column, Integer, String, Text, select
        from sqlalchemy.orm import DeclarativeBase

        class _KBase(DeclarativeBase):
            pass

        class _KAnime(_KBase):
            __tablename__ = "animes"
            id = Column(Integer, primary_key=True)
            title = Column(String(255))
            season = Column(Integer, default=1)

        async with _KaworaiSessionLocal() as session:
            result = await session.execute(select(_KAnime))
            all_anime = result.scalars().all()

        for anime in all_anime:
            anime_title = anime.title or ""
            base = _strip_season_suffix(anime_title).lower().strip()
            if not base:
                continue
            if base == name_normalized:
                if season is not None:
                    anime_season = int(anime.season or 1)
                    if anime_season == season:
                        return anime.id, anime_title
                else:
                    return anime.id, anime_title

        # Fallback: faslsiz mos kelishini qidirish
        if season is not None:
            for anime in all_anime:
                anime_title = anime.title or ""
                base = _strip_season_suffix(anime_title).lower().strip()
                if base == name_normalized:
                    return anime.id, anime_title

        return None
    except Exception:
        log.exception("Kaworai DB dan anime qidirishda xato")
        return None
