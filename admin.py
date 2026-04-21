# admin.py - Админ-панель для тестового бота RadCoin Buddy
# Версия: 0.1.0

from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from config import logger, ADMIN_CODE, SUPER_ADMIN_IDS
from core import is_admin
from database import Session, User, Clan


# ==================== ВЫДАЧА ПРАВ ====================

async def admin_giveme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить админ-права по коду"""
    if not context.args:
        await update.message.reply_text("❌ /givemeplsadmin [код]")
        return
    
    if context.args[0] == ADMIN_CODE:
        session = Session()
        try:
            user = session.query(User).filter_by(user_id=update.effective_user.id).first()
            if not user:
                user = User(user_id=update.effective_user.id, username=update.effective_user.username)
                session.add(user)
            user.is_admin = True
            user.is_blocked = False
            session.commit()
            await update.message.reply_text("✅ *Админ-права получены!*", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in admin_giveme: {e}")
            await update.message.reply_text("❌ Ошибка")
        finally:
            Session.remove()
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
    session = Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return
        
        if resource == 'RC':
            user.radcoins += amount
            session.commit()
            await update.message.reply_text(f"✅ *Выдано {amount} RC @{username}*", parse_mode='Markdown')
            
        elif resource == 'RF':
            user.radfragments += amount
            session.commit()
            await update.message.reply_text(f"✅ *Выдано {amount} RF @{username}*", parse_mode='Markdown')
            
        elif resource == 'RCR':
            # Кристаллы идут в казну клана
            if user.clan_id:
                clan = session.query(Clan).filter_by(id=user.clan_id).first()
                if clan:
                    clan.treasury_crystals += amount
                    session.commit()
                    await update.message.reply_text(
                        f"✅ *Выдано {amount} кристаллов в казну клана {clan.name}!*\n"
                        f"📊 Теперь в казне: {clan.treasury_crystals} кристаллов",
                        parse_mode='Markdown'
                    )
                else:
                    user.radcrystals += amount
                    session.commit()
                    await update.message.reply_text(f"✅ *Выдано {amount} кристаллов лично @{username}*", parse_mode='Markdown')
            else:
                user.radcrystals += amount
                session.commit()
                await update.message.reply_text(f"✅ *Выдано {amount} кристаллов лично @{username}*", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Доступно: RC, RF, RCr")
            return
        
        # Уведомление игрока
        try:
            await context.bot.send_message(
                user.user_id,
                f"💰 *Администратор выдал вам {amount} {resource}!*",
                parse_mode='Markdown'
            )
        except:
            pass
        
    except Exception as e:
        logger.error(f"Error in admin_give: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


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
    session = Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return
        
        if resource == 'RC':
            if user.radcoins < amount:
                await update.message.reply_text(f"❌ У @{username} {user.radcoins:.0f} RC")
                return
            user.radcoins -= amount
        elif resource == 'RF':
            if user.radfragments < amount:
                await update.message.reply_text(f"❌ У @{username} {user.radfragments} RF")
                return
            user.radfragments -= amount
        elif resource == 'RCR':
            if user.radcrystals < amount:
                await update.message.reply_text(f"❌ У @{username} {user.radcrystals} RCr")
                return
            user.radcrystals -= amount
        else:
            await update.message.reply_text("❌ RC, RF или RCr")
            return
        
        session.commit()
        await update.message.reply_text(f"✅ *Забрано {amount} {resource} у @{username}*", parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in admin_take: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== УПРАВЛЕНИЕ УРОВНЕМ ====================

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
    
    session = Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return
        
        old_level = user.level
        user.level = level
        session.commit()
        
        await update.message.reply_text(f"📈 *@{username}: {old_level} → {level} уровень*", parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in admin_setlevel: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== ПРОСМОТР ИГРОКОВ ====================

async def admin_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список всех игроков"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    
    session = Session()
    try:
        users = session.query(User).order_by(User.level.desc()).all()
        if not users:
            await update.message.reply_text("📋 *Нет игроков*", parse_mode='Markdown')
            return
        
        text = "👥 *Список игроков*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, u in enumerate(users, 1):
            clan_name = "—"
            if u.clan_id:
                clan = session.query(Clan).filter_by(id=u.clan_id).first()
                if clan:
                    clan_name = clan.name
            text += f"{i}. *{u.username or f'ID:{u.user_id}'}* — ур.{u.level}, 🏰{clan_name}\n"
            
            if len(text) > 3500:
                await update.message.reply_text(text, parse_mode='Markdown')
                text = ""
        
        if text:
            await update.message.reply_text(text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in admin_players: {e}")
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== АДМИНЫ ====================

async def admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список администраторов"""
    session = Session()
    try:
        admins_list = session.query(User).filter(User.is_admin == True).all()
        if not admins_list:
            await update.message.reply_text("📋 *Нет администраторов*", parse_mode='Markdown')
            return
        
        text = "👑 *Администраторы*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, a in enumerate(admins_list, 1):
            main = " (ГЛАВНЫЙ)" if a.user_id in SUPER_ADMIN_IDS else ""
            text += f"{i}. *{a.username or f'ID:{a.user_id}'}*{main}\n"
        await update.message.reply_text(text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in admins: {e}")
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()
