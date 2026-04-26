"""Motivatsion xabarlar — dangasalik aniqlanganda yoki streak buzilganda."""

from __future__ import annotations

import random

# 15+ daqiqa javob bo'lmaganda — qattiq gap
NUDGE_MESSAGES: list[str] = [
    "Tur. Hozir. Keyin o'ylaysan.",
    "Ertaga yo'q. Hozir bor.",
    "Kim uchun ishlayapsan? Esla.",
    "Vaqt kutmaydi. Tur va qil.",
    "10 daqiqa bo'lsa ham — boshla.",
    "Dangasalik g'animning — uni yeng.",
    "Kecha aytgan edingmi 'ertadan boshlayman' deb? Mana bugun.",
    "Har bir katta natija kichik qadamdan boshlangan.",
    "O'zingni aldama. Tur.",
    "Hozir qilmasan, qachon qilasan?",
]

# Bajarganida — rag'bat
DONE_MESSAGES: list[str] = [
    "Zo'r! Davom et.",
    "Barakalla! Shu ruhda.",
    "Ajoyib. Keyingisiga o'taman.",
    "Ha, shunaqa bo'lishi kerak!",
    "Kuchli!",
    "Yaxshi ish.",
    "Bajarildi. Sen buni qila olasan.",
]

# Skip qilganda
SKIP_RESPONSES: list[str] = [
    "Nega? Bir gap bilan ayt.",
    "Sababi nima?",
    "Nima bo'ldi? Ayt.",
]

# Skip sababi aytilganda
SKIP_REASON_ACKS: list[str] = [
    "Yaxshi. Hozir boshla. 10 daqiqa bo'lsa ham.",
    "Tushundim. Lekin keyingisini o'tkazma.",
    "OK. Ammo o'zingni aldama — bugun yana urinib ko'r.",
    "Tushunarli. Keyingisiga tayyor bo'l.",
]

# Streak buzilganda
STREAK_BROKEN_TEMPLATE = "{streak} kunlik streak ketdi. Bugun qaytadan boshla."

# Streak davom etayotganda
STREAK_GOING: list[str] = [
    "Davom etayapsan! Shu ruhda!",
    "Kuchli! Streak o'sayapti!",
    "To'xtama! Davom et!",
]


def random_nudge() -> str:
    return random.choice(NUDGE_MESSAGES)


def random_done() -> str:
    return random.choice(DONE_MESSAGES)


def random_skip_ask() -> str:
    return random.choice(SKIP_RESPONSES)


def random_skip_ack() -> str:
    return random.choice(SKIP_REASON_ACKS)


def streak_broken_msg(streak: int) -> str:
    return STREAK_BROKEN_TEMPLATE.format(streak=streak)


def random_streak_going() -> str:
    return random.choice(STREAK_GOING)
