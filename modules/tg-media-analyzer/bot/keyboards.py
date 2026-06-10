"""Inline keyboards for media analyzer bot."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def action_keyboard(store_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🚀 В работу",   callback_data=f"s:{store_key}"),
        InlineKeyboardButton("📌 Отложить",   callback_data=f"d:{store_key}"),
        InlineKeyboardButton("❌ Пропустить", callback_data=f"x:{store_key}"),
    ]])


def empty_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([])
