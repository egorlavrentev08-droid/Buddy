# clan.py - Кланы для тестового бота (упрощённая версия)
# Версия: 0.1.0

from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from config import logger
from core import send_to_private, is_admin
from database import (
    get_user, save_user, get_all_users,
    create_clan, get_clan, get_clan_by_name, get_all_clans, save_clan,
    update_user_clan
)


# ==================== КЛАНЫ ====================

async def clan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главная команда кланов"""
    if not context.args:
        await update.message.reply_text(
            "🏰 *Кланы Пустоши*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "/clan create [название] — создать (2ур, 1000RC)\n"
            "/clan join [название] — вступить\n"
            "/clan info — информация о клане\n"
            "/clan invest [сумма] — вложить RC в казну\n"
            "/clan withdraw [сумма] — снять RC (лидер)\n"
            "/clan give @ник [сумма] — выдать RC (лидер)\n"
            "/clan list — список кланов\n"
            "/clan players [название] — список участников\n"
            "/clan goodbye — распустить клан (дважды)\n\n"
            "🏗️ *Клановый город:*\n"
            "/city — карта города\n"
            "/city build [координаты] [здание] — построить\n"
            "/city upgrade [здание] — улучшить\n"
            "/city info [координаты] — информация о клетке",
            parse_mode='Markdown'
        )
        return
    
    action = context.args[0].lower()
    
    if action == "create":
        await clan_create(update, context)
    elif action == "join":
        await clan_join(update, context)
    elif action == "info":
        await clan_info(update, context)
    elif action == "invest":
        await clan_invest(update, context)
    elif action == "withdraw":
        await clan_withdraw(update, context)
    elif action == "give":
        await clan_give(update, context)
    elif action == "list":
        await clan_list(update, context)
    elif action == "players":
        await clan_players(update, context)
    elif action == "goodbye":
        await clan_goodbye(update, context)
    else:
        await update.message.reply_text("❌ Неизвестная команда")


async def clan_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создать клан"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ /clan create [название]")
        return
    name = ' '.join(context.args[1:])
    if len(name) > 30:
        await update.message.reply_text("❌ Название до 30 символов")
        return
    
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if user.get('clan_id'):
        await update.message.reply_text("❌ Вы уже в клане")
        return
    
    if user.get('level', 1) < 2:
        await update.message.reply_text("❌ Для создания клана нужен 2 уровень")
        return
    
    if user.get('radcoins', 0) < 1000:
        await update.message.reply_text(f"❌ Нужно 1000 RC, у вас {user.get('radcoins', 0):.0f}")
        return
    
    existing = get_clan_by_name(name)
    if existing:
        await update.message.reply_text("❌ Клан с таким названием уже существует")
        return
    
    clan = create_clan(name, user_id)
    
    # Обновляем пользователя
    user['clan_id'] = clan['id']
    user['radcoins'] -= 1000
    save_user(user)
    
    await update.message.reply_text(f"🏰 *Клан {name} создан!*\n\n💡 Теперь вы можете строить клановый город: `/city`", parse_mode='Markdown')


async def clan_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вступить в клан"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ /clan join [название]")
        return
    name = ' '.join(context.args[1:])
    
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if user.get('clan_id'):
        await update.message.reply_text("❌ Вы уже в клане")
        return
    
    clan = get_clan_by_name(name)
    if not clan:
        await update.message.reply_text("❌ Клан не найден")
        return
    
    user['clan_id'] = clan['id']
    save_user(user)
    
    await update.message.reply_text(f"✅ *Вы вступили в клан {clan['name']}!*", parse_mode='Markdown')


async def clan_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о клане"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user.get('clan_id'):
        await update.message.reply_text("❌ Вы не в клане")
        return
    
    clan = get_clan(user['clan_id'])
    if not clan:
        await update.message.reply_text("❌ Клан не найден")
        return
    
    members = [u for u in get_all_users() if u.get('clan_id') == clan['id']]
    leader = next((u for u in members if u['user_id'] == clan['leader_id']), None)
    
    text = (
        f"🏰 *{clan['name']}*\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 *Лидер:* @{leader['username'] if leader else '?'}\n"
        f"👥 *Участников:* {len(members)}\n"
        f"💰 *Казна:* {clan.get('treasury_coins', 0):.0f} RC\n"
        f"💎 *Кристаллы:* {clan.get('treasury_crystals', 0)}\n\n"
        f"🏗️ *Клановый город:* `/city`"
    )
    await update.message.reply_text(text, parse_mode='Markdown')


async def clan_invest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Инвестировать в казну клана"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ /clan invest [сумма]")
        return
    
    try:
        amount = int(context.args[1])
        if amount <= 0:
            await update.message.reply_text("❌ Положительная сумма")
            return
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return
    
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user.get('clan_id'):
        await update.message.reply_text("❌ Вы не в клане")
        return
    
    clan = get_clan(user['clan_id'])
    if not clan:
        await update.message.reply_text("❌ Клан не найден")
        return
    
    if user.get('radcoins', 0) < amount:
        await update.message.reply_text(f"❌ Не хватает! У вас {user.get('radcoins', 0):.0f} RC")
        return
    
    user['radcoins'] -= amount
    clan['treasury_coins'] = clan.get('treasury_coins', 0) + amount
    save_user(user)
    save_clan(clan)
    
    await update.message.reply_text(f"💰 *Инвестировано {amount} RC в {clan['name']}*", parse_mode='Markdown')


async def clan_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Снять средства из казны (только лидер)"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ /clan withdraw [сумма]")
        return
    
    try:
        amount = int(context.args[1])
        if amount <= 0:
            await update.message.reply_text("❌ Положительная сумма")
            return
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return
    
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user.get('clan_id'):
        await update.message.reply_text("❌ Вы не в клане")
        return
    
    clan = get_clan(user['clan_id'])
    if not clan:
        await update.message.reply_text("❌ Клан не найден")
        return
    
    if clan['leader_id'] != user_id:
        await update.message.reply_text("❌ Только лидер может снимать средства")
        return
    
    if clan.get('treasury_coins', 0) < amount:
        await update.message.reply_text(f"❌ В казне {clan.get('treasury_coins', 0):.0f} RC")
        return
    
    clan['treasury_coins'] -= amount
    user['radcoins'] = user.get('radcoins', 0) + amount
    save_clan(clan)
    save_user(user)
    
    await update.message.reply_text(
        f"💰 *Снято {amount} RC из казны*\n\n"
        f"🏰 Клан: {clan['name']}\n"
        f"📊 Остаток: {clan.get('treasury_coins', 0):.0f} RC",
        parse_mode='Markdown'
    )


async def clan_give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдать средства участнику (только лидер)"""
    if len(context.args) < 3:
        await update.message.reply_text("❌ /clan give @ник [сумма]")
        return
    
    username = context.args[1].lstrip('@')
    try:
        amount = int(context.args[2])
        if amount <= 0:
            await update.message.reply_text("❌ Положительная сумма")
            return
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return
    
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user.get('clan_id'):
        await update.message.reply_text("❌ Вы не в клане")
        return
    
    clan = get_clan(user['clan_id'])
    if not clan:
        await update.message.reply_text("❌ Клан не найден")
        return
    
    if clan['leader_id'] != user_id:
        await update.message.reply_text("❌ Только лидер может выдавать средства")
        return
    
    target = next((u for u in get_all_users() if u.get('username') == username), None)
    if not target or target.get('clan_id') != clan['id']:
        await update.message.reply_text(f"❌ @{username} не состоит в клане")
        return
    
    if clan.get('treasury_coins', 0) < amount:
        await update.message.reply_text(f"❌ В казне {clan.get('treasury_coins', 0):.0f} RC")
        return
    
    clan['treasury_coins'] -= amount
    target['radcoins'] = target.get('radcoins', 0) + amount
    save_clan(clan)
    save_user(target)
    
    await update.message.reply_text(
        f"💰 *Выдано {amount} RC участнику @{username}*\n\n"
        f"🏰 Клан: {clan['name']}\n"
        f"📊 Остаток: {clan.get('treasury_coins', 0):.0f} RC",
        parse_mode='Markdown'
    )
    
    try:
        await context.bot.send_message(
            target['user_id'],
            f"💰 *Вам выдали {amount} RC из казны клана {clan['name']}!*",
            parse_mode='Markdown'
        )
    except:
        pass


async def clan_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список кланов"""
    clans = get_all_clans()
    if not clans:
        await update.message.reply_text("📋 *Нет кланов*", parse_mode='Markdown')
        return
    
    text = "📋 *Список кланов*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for clan in clans:
        members = [u for u in get_all_users() if u.get('clan_id') == clan['id']]
        text += f"🏰 *{clan['name']}* — 👥 {len(members)}\n"
    await update.message.reply_text(text, parse_mode='Markdown')


async def clan_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список игроков в клане"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ /clan players [название клана]")
        return
    
    clan_name = ' '.join(context.args[1:])
    clan = get_clan_by_name(clan_name)
    if not clan:
        await update.message.reply_text(f"❌ Клан '{clan_name}' не найден!")
        return
    
    members = [u for u in get_all_users() if u.get('clan_id') == clan['id']]
    if not members:
        await update.message.reply_text(f"📋 В клане '{clan_name}' нет участников")
        return
    
    leader = next((u for u in members if u['user_id'] == clan['leader_id']), None)
    
    text = f"🏰 *{clan['name']}*\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"👑 *Лидер:* @{leader['username'] if leader else '?'}\n"
    text += f"👥 *Участников:* {len(members)}\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, member in enumerate(members, 1):
        role = "👑 Лидер" if member['user_id'] == clan['leader_id'] else "🔹 Участник"
        text += f"{i}. *{member.get('username', f'ID:{member['user_id']}')}* — {role}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')


async def clan_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Распустить клан (только лидер)"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user.get('clan_id'):
        await update.message.reply_text("❌ Вы не в клане")
        return
    
    clan = get_clan(user['clan_id'])
    if not clan:
        await update.message.reply_text("❌ Клан не найден")
        return
    
    if clan['leader_id'] != user_id:
        await update.message.reply_text("❌ Только лидер")
        return
    
    if not context.user_data.get('confirm_clan_delete'):
        context.user_data['confirm_clan_delete'] = True
        await update.message.reply_text(f"⚠️ *Распустить {clan['name']}?* /clan goodbye ещё раз", parse_mode='Markdown')
        return
    
    context.user_data.pop('confirm_clan_delete')
    
    # Удаляем клан у всех участников
    for member in get_all_users():
        if member.get('clan_id') == clan['id']:
            member['clan_id'] = None
            save_user(member)
    
    # Удаляем клан из базы (в упрощённой версии просто помечаем или удаляем)
    from database import load_data, save_data
    data = load_data()
    if str(clan['id']) in data['clans']:
        del data['clans'][str(clan['id'])]
        save_data(data)
    
    await update.message.reply_text(f"🏰 *Клан {clan['name']} распущен*", parse_mode='Markdown')
