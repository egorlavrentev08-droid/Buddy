# clan.py - Кланы для тестового бота RadCoin Buddy
# Версия: 0.1.0

from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from config import logger, MAX_CLAN_BONUS
from core import send_to_private, is_admin
from database import Session, User, Clan


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
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ /start")
            return
        if user.clan_id:
            await update.message.reply_text("❌ Вы уже в клане")
            return
        if user.level < 2:
            await update.message.reply_text("❌ Для создания клана нужен 2 уровень")
            return
        if user.radcoins < 1000:
            await update.message.reply_text(f"❌ Нужно 1000 RC, у вас {user.radcoins:.0f}")
            return
        
        existing = session.query(Clan).filter_by(name=name).first()
        if existing:
            await update.message.reply_text("❌ Клан с таким названием уже существует")
            return
        
        clan = Clan(name=name, leader_id=user.user_id)
        session.add(clan)
        session.flush()
        user.clan_id = clan.id
        user.radcoins -= 1000
        session.commit()
        
        await update.message.reply_text(f"🏰 *Клан {name} создан!*\n\n💡 Теперь вы можете строить клановый город: `/city`", parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in clan_create: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


async def clan_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вступить в клан"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ /clan join [название]")
        return
    name = ' '.join(context.args[1:])
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ /start")
            return
        if user.clan_id:
            await update.message.reply_text("❌ Вы уже в клане")
            return
        
        clan = session.query(Clan).filter_by(name=name).first()
        if not clan:
            await update.message.reply_text("❌ Клан не найден")
            return
        
        user.clan_id = clan.id
        session.commit()
        await update.message.reply_text(f"✅ *Вы вступили в клан {clan.name}!*", parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in clan_join: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


async def clan_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о клане"""
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user or not user.clan_id:
            await update.message.reply_text("❌ Вы не в клане")
            return
        
        clan = session.query(Clan).filter_by(id=user.clan_id).first()
        if not clan:
            await update.message.reply_text("❌ Клан не найден")
            return
        
        members = session.query(User).filter_by(clan_id=clan.id).count()
        leader = session.query(User).filter_by(user_id=clan.leader_id).first()
        
        text = (
            f"🏰 *{clan.name}*\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👑 *Лидер:* @{leader.username if leader else '?'}\n"
            f"👥 *Участников:* {members}\n"
            f"💰 *Казна:* {clan.treasury_coins:.0f} RC\n"
            f"💎 *Кристаллы:* {clan.treasury_crystals}\n\n"
            f"🏗️ *Клановый город:* `/city`"
        )
        await update.message.reply_text(text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in clan_info: {e}")
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


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
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user or not user.clan_id:
            await update.message.reply_text("❌ Вы не в клане")
            return
        
        clan = session.query(Clan).filter_by(id=user.clan_id).first()
        if not clan:
            await update.message.reply_text("❌ Клан не найден")
            return
        
        if user.radcoins < amount:
            await update.message.reply_text(f"❌ Не хватает! У вас {user.radcoins:.0f} RC")
            return
        
        user.radcoins -= amount
        clan.treasury_coins += amount
        session.commit()
        
        await update.message.reply_text(f"💰 *Инвестировано {amount} RC в {clan.name}*", parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in clan_invest: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


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
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user or not user.clan_id:
            await update.message.reply_text("❌ Вы не в клане")
            return
        
        clan = session.query(Clan).filter_by(id=user.clan_id).first()
        if not clan:
            await update.message.reply_text("❌ Клан не найден")
            return
        
        if clan.leader_id != user.user_id:
            await update.message.reply_text("❌ Только лидер может снимать средства")
            return
        
        if clan.treasury_coins < amount:
            await update.message.reply_text(f"❌ В казне {clan.treasury_coins:.0f} RC")
            return
        
        clan.treasury_coins -= amount
        user.radcoins += amount
        session.commit()
        
        await update.message.reply_text(
            f"💰 *Снято {amount} RC из казны*\n\n"
            f"🏰 Клан: {clan.name}\n"
            f"📊 Остаток: {clan.treasury_coins:.0f} RC",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in clan_withdraw: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


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
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user or not user.clan_id:
            await update.message.reply_text("❌ Вы не в клане")
            return
        
        clan = session.query(Clan).filter_by(id=user.clan_id).first()
        if not clan:
            await update.message.reply_text("❌ Клан не найден")
            return
        
        if clan.leader_id != user.user_id:
            await update.message.reply_text("❌ Только лидер может выдавать средства")
            return
        
        target = session.query(User).filter_by(username=username).first()
        if not target or target.clan_id != clan.id:
            await update.message.reply_text(f"❌ @{username} не состоит в клане")
            return
        
        if clan.treasury_coins < amount:
            await update.message.reply_text(f"❌ В казне {clan.treasury_coins:.0f} RC")
            return
        
        clan.treasury_coins -= amount
        target.radcoins += amount
        session.commit()
        
        await update.message.reply_text(
            f"💰 *Выдано {amount} RC участнику @{username}*\n\n"
            f"🏰 Клан: {clan.name}\n"
            f"📊 Остаток: {clan.treasury_coins:.0f} RC",
            parse_mode='Markdown'
        )
        
        try:
            await context.bot.send_message(
                target.user_id,
                f"💰 *Вам выдали {amount} RC из казны клана {clan.name}!*",
                parse_mode='Markdown'
            )
        except:
            pass
        
    except Exception as e:
        logger.error(f"Error in clan_give: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


async def clan_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список кланов"""
    session = Session()
    try:
        clans = session.query(Clan).order_by(Clan.created_at).all()
        if not clans:
            await update.message.reply_text("📋 *Нет кланов*", parse_mode='Markdown')
            return
        
        text = "📋 *Список кланов*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for clan in clans:
            members = session.query(User).filter_by(clan_id=clan.id).count()
            text += f"🏰 *{clan.name}* — 👥 {members}\n"
        await update.message.reply_text(text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in clan_list: {e}")
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


async def clan_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список игроков в клане"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ /clan players [название клана]")
        return
    
    clan_name = ' '.join(context.args[1:])
    session = Session()
    try:
        clan = session.query(Clan).filter_by(name=clan_name).first()
        if not clan:
            await update.message.reply_text(f"❌ Клан '{clan_name}' не найден!")
            return
        
        members = session.query(User).filter_by(clan_id=clan.id).order_by(User.level.desc()).all()
        if not members:
            await update.message.reply_text(f"📋 В клане '{clan_name}' нет участников")
            return
        
        leader = session.query(User).filter_by(user_id=clan.leader_id).first()
        
        text = f"🏰 *{clan.name}*\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"👑 *Лидер:* @{leader.username if leader else '?'}\n"
        text += f"👥 *Участников:* {len(members)}\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, member in enumerate(members, 1):
            role = "👑 Лидер" if member.user_id == clan.leader_id else "🔹 Участник"
            text += f"{i}. *{member.username or f'ID:{member.user_id}'}* — {role}\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in clan_players: {e}")
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


async def clan_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Распустить клан (только лидер)"""
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user or not user.clan_id:
            await update.message.reply_text("❌ Вы не в клане")
            return
        
        clan = session.query(Clan).filter_by(id=user.clan_id).first()
        if not clan:
            await update.message.reply_text("❌ Клан не найден")
            return
        
        if clan.leader_id != user.user_id:
            await update.message.reply_text("❌ Только лидер")
            return
        
        if not context.user_data.get('confirm_clan_delete'):
            context.user_data['confirm_clan_delete'] = True
            await update.message.reply_text(f"⚠️ *Распустить {clan.name}?* /clan goodbye ещё раз", parse_mode='Markdown')
            return
        
        context.user_data.pop('confirm_clan_delete')
        
        members = session.query(User).filter_by(clan_id=clan.id).all()
        for member in members:
            member.clan_id = None
        
        session.delete(clan)
        session.commit()
        
        await update.message.reply_text(f"🏰 *Клан {clan.name} распущен*", parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in clan_goodbye: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()
