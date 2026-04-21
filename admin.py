# admin.py - Админ-панель для тестового бота RadCoin Buddy
# Версия: 0.1.0

from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from config import logger, ADMIN_CODE, SUPER_ADMIN_IDS
from core import is_admin
from database import get_user, save_user, get_all_users, get_clan, save_clan, get_all_clans


# ==================== ВЫДАЧА ПРАВ ====================

async def admin_giveme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить админ-права по коду"""
    if not context.args:
        await update.message.reply_text("❌ /givemeplsadmin [код]")
        return
    
    if context.args[0] == ADMIN_CODE:
        user_id = update.effective_user.id
        user = get_user(user_id)
        user['is_admin'] = True
        user['is_blocked'] = False
        save_user(user)
        await update.message.reply_text("✅ *Админ-права получены!*", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ *Неверный код!*", parse_mode='Markdown')


# ==================== УПРАВЛЕНИЕ РЕСУРСАМИ ====================

async def admin_give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдать ресурсы игроку (RC, RF, RCr)"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    
    if len(context.args) < 3:
        await update.message.reply_text("❌ /give @ник [сумма] {RC,RF,RCr}\n\nRCr — кристаллы (идут в казну клана)", parse_mode='Markdown')
        return
    
    username = context.args[0].lstrip('@')
    try:
        amount = int(context.args[1])
        if amount <= 0:
            await update.message.reply_text("❌ Положительная сумма")
            return
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return
    
    resource = context.args[2].upper()
    
    users = get_all_users()
    target = next((u for u in users if u.get('username') == username), None)
    if not target:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    if resource == 'RC':
        target['radcoins'] = target.get('radcoins', 0) + amount
        save_user(target)
        await update.message.reply_text(f"✅ *Выдано {amount} RC @{username}*", parse_mode='Markdown')
        
    elif resource == 'RF':
        target['radfragments'] = target.get('radfragments', 0) + amount
        save_user(target)
        await update.message.reply_text(f"✅ *Выдано {amount} RF @{username}*", parse_mode='Markdown')
        
    elif resource == 'RCR':
        if target.get('clan_id'):
            clan = get_clan(target['clan_id'])
            if clan:
                clan['treasury_crystals'] = clan.get('treasury_crystals', 0) + amount
                save_clan(clan)
                await update.message.reply_text(
                    f"✅ *Выдано {amount} кристаллов в казну клана {clan['name']}!*\n"
                    f"📊 Теперь в казне: {clan['treasury_crystals']} кристаллов",
                    parse_mode='Markdown'
                )
            else:
                target['radcrystals'] = target.get('radcrystals', 0) + amount
                save_user(target)
                await update.message.reply_text(f"✅ *Выдано {amount} кристаллов лично @{username}*", parse_mode='Markdown')
        else:
            target['radcrystals'] = target.get('radcrystals', 0) + amount
            save_user(target)
            await update.message.reply_text(f"✅ *Выдано {amount} кристаллов лично @{username}*", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Доступно: RC, RF, RCr")
        return
    
    try:
        await context.bot.send_message(
            target['user_id'],
            f"💰 *Администратор выдал вам {amount} {resource}!*",
            parse_mode='Markdown'
        )
    except:
        pass


async def admin_take(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Забрать ресурсы у игрока"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    
    if len(context.args) < 3:
        await update.message.reply_text("❌ /take @ник [сумма] {RC,RF,RCr}")
        return
    
    username = context.args[0].lstrip('@')
    try:
        amount = int(context.args[1])
        if amount <= 0:
            await update.message.reply_text("❌ Положительная сумма")
            return
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return
    
    resource = context.args[2].upper()
    
    users = get_all_users()
    target = next((u for u in users if u.get('username') == username), None)
    if not target:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    if resource == 'RC':
        if target.get('radcoins', 0) < amount:
            await update.message.reply_text(f"❌ У @{username} {target.get('radcoins', 0):.0f} RC")
            return
        target['radcoins'] = target.get('radcoins', 0) - amount
    elif resource == 'RF':
        if target.get('radfragments', 0) < amount:
            await update.message.reply_text(f"❌ У @{username} {target.get('radfragments', 0)} RF")
            return
        target['radfragments'] = target.get('radfragments', 0) - amount
    elif resource == 'RCR':
        if target.get('radcrystals', 0) < amount:
            await update.message.reply_text(f"❌ У @{username} {target.get('radcrystals', 0)} RCr")
            return
        target['radcrystals'] = target.get('radcrystals', 0) - amount
    else:
        await update.message.reply_text("❌ RC, RF или RCr")
        return
    
    save_user(target)
    await update.message.reply_text(f"✅ *Забрано {amount} {resource} у @{username}*", parse_mode='Markdown')


async def admin_setlevel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить уровень игроку"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ /setlevel @ник [уровень]")
        return
    
    username = context.args[0].lstrip('@')
    try:
        level = int(context.args[1])
        if level < 1 or level > 100:
            await update.message.reply_text("❌ Уровень от 1 до 100")
            return
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return
    
    users = get_all_users()
    target = next((u for u in users if u.get('username') == username), None)
    if not target:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    old_level = target.get('level', 1)
    target['level'] = level
    save_user(target)
    
    await update.message.reply_text(f"📈 *@{username}: {old_level} → {level} уровень*", parse_mode='Markdown')


async def admin_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список всех игроков"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    
    users = get_all_users()
    if not users:
        await update.message.reply_text("📋 *Нет игроков*", parse_mode='Markdown')
        return
    
    text = "👥 *Список игроков*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, u in enumerate(users, 1):
        clan_name = "—"
        if u.get('clan_id'):
            clan = get_clan(u['clan_id'])
            if clan:
                clan_name = clan['name']
        user_name = u.get('username', f"ID:{u['user_id']}")
        text += f"{i}. *{user_name}* — ур.{u.get('level', 1)}, 🏰{clan_name}\n"
        
        if len(text) > 3500:
            await update.message.reply_text(text, parse_mode='Markdown')
            text = ""
    
    if text:
        await update.message.reply_text(text, parse_mode='Markdown')


async def admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список администраторов"""
    users = get_all_users()
    admins_list = [u for u in users if u.get('is_admin')]
    
    if not admins_list:
        await update.message.reply_text("📋 *Нет администраторов*", parse_mode='Markdown')
        return
    
    text = "👑 *Администраторы*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, a in enumerate(admins_list, 1):
        main = " (ГЛАВНЫЙ)" if a['user_id'] in SUPER_ADMIN_IDS else ""
        admin_name = a.get('username', f"ID:{a['user_id']}")
        text += f"{i}. *{admin_name}*{main}\n"
    await update.message.reply_text(text, parse_mode='Markdown')


# ==================== ПРОСМОТР КЛАНОВ (АДМИН) ====================

async def admin_clans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список всех кланов (админ)"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    
    clans = get_all_clans()
    if not clans:
        await update.message.reply_text("📋 *Нет кланов*", parse_mode='Markdown')
        return
    
    text = "🏰 *Список кланов*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, clan in enumerate(clans, 1):
        members_count = len([u for u in get_all_users() if u.get('clan_id') == clan['id']])
        text += f"{i}. *{clan['name']}* — 👥 {members_count}, 💎 {clan.get('treasury_crystals', 0)}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')


async def admin_clan_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о клане (админ)"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("❌ /admin_clan_info [название клана]")
        return
    
    clan_name = ' '.join(context.args)
    clan = get_clan_by_name(clan_name)
    if not clan:
        await update.message.reply_text(f"❌ Клан '{clan_name}' не найден!")
        return
    
    members = [u for u in get_all_users() if u.get('clan_id') == clan['id']]
    leader = next((u for u in members if u['user_id'] == clan['leader_id']), None)
    
    text = (
        f"🏰 *{clan['name']}*\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 *Лидер:* @{leader['username'] if leader else '?'}\n"
        f"👥 *Участников:* {len(members)}\n"
        f"💰 *Казна:* {clan.get('treasury_coins', 0):.0f} RC\n"
        f"💎 *Кристаллы:* {clan.get('treasury_crystals', 0)}\n"
        f"🏗️ *Построек:* {len(clan.get('buildings', {}))}\n"
    )
    await update.message.reply_text(text, parse_mode='Markdown')
