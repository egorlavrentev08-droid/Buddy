# user.py - Базовые команды пользователя (тестовый бот)
# Версия: 0.1.0

from telegram import Update
from telegram.ext import ContextTypes

from config import logger
from core import send_to_private
from database import get_user, save_user


# ==================== СТАРТ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Стартовая команда"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    user = get_user(user_id, username)
    
    # Бонус новичка (если новый игрок)
    if user.get('radcoins', 0) == 0:
        user['radcoins'] = 1000
        save_user(user)
        await update.message.reply_text(
            "🌟 *RadCoin Buddy — Тестовый полигон*\n\n"
            "🎁 *Бонус новичка: 1000 RC!*\n\n"
            "🏰 /clan — создать или вступить в клан\n"
            "🏗️ /city — построить клановый город\n"
            "💰 /give — выдать ресурсы (админ)\n\n"
            "📖 *Команды:*\n"
            "/help — справка\n"
            "/profile — профиль",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "🌟 *RadCoin Buddy — Тестовый полигон*\n\n"
            "🏰 /clan — управление кланом\n"
            "🏗️ /city — клановый город\n"
            "📖 /help — справка",
            parse_mode='Markdown'
        )


# ==================== ПОМОЩЬ ====================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка"""
    text = (
        "📖 *RadCoin Buddy — Справка*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*🏰 КЛАНЫ*\n"
        "/clan create [название] — создать клан\n"
        "/clan join [название] — вступить в клан\n"
        "/clan info — информация о клане\n"
        "/clan invest [сумма] — вложить RC в казну\n"
        "/clan list — список кланов\n"
        "/clan players [название] — список участников\n\n"
        "*🏗️ КЛАНОВЫЙ ГОРОД*\n"
        "/city — карта города\n"
        "/city build [координаты] [здание] — построить\n"
        "/city upgrade [здание] — улучшить\n"
        "/city info [координаты] — информация о клетке\n\n"
        "*👤 ПРОФИЛЬ*\n"
        "/profile — ваш профиль\n\n"
        "*👑 АДМИН*\n"
        "/givemeplsadmin [код] — получить админку\n"
        "/give @ник [сумма] RC/RF/RCr — выдать ресурсы\n"
        "/players — список игроков\n"
        "/admins — список админов"
    )
    await send_to_private(update, context, text)


# ==================== ПРОФИЛЬ ====================

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Профиль пользователя"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    from database import get_clan
    clan_name = "—"
    if user.get('clan_id'):
        clan = get_clan(user['clan_id'])
        if clan:
            clan_name = clan['name']
    
    text = (
        f"👤 *{user.get('username', f'ID:{user_id}')}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"☢️ *РадКоины:* {user.get('radcoins', 0):.0f}\n"
        f"☣️ *РадФрагменты:* {user.get('radfragments', 0)}\n"
        f"💎 *Кристаллы:* {user.get('radcrystals', 0)}\n"
        f"⚠️ *Уровень:* {user.get('level', 1)}\n"
        f"🏰 *Клан:* {clan_name}"
    )
    await send_to_private(update, context, text)
