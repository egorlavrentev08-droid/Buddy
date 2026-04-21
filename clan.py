# clan.py - Кланы и радио
# Версия: 2.0.0

import random
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
            "/clan join [название] — вступить (1ур)\n"
            "/clan info — информация\n"
            "/clan invest [сумма] — вложить RC\n"
            "/clan withdraw [сумма] — снять RC (лидер)\n"
            "/clan give @ник [сумма] — выдать RC участнику (лидер)\n"
            "/clan up [коллектор/опыт/удвоение] — улучшить\n"
            "/clan list — список кланов\n"
            "/clan players [название] — список участников\n"
            "/clan goodbye — распустить (дважды)",
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
    elif action == "up":
        await clan_upgrade(update, context)
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
            await update.message.reply_text("❌ Сначала /start")
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
        await update.message.reply_text(f"🏰 *Клан {name} создан!*", parse_mode='Markdown')
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
            f"📈 *Улучшения:*\n"
            f"  • +{clan.collect_bonus}% к сбору\n"
            f"  • +{clan.exp_bonus * 5}% к опыту\n"
            f"  • +{clan.double_bonus}% к удвоению"
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

async def clan_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Улучшить клан (только лидер)"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ /clan up [коллектор/опыт/удвоение]")
        return
    upgrade = context.args[1].lower()
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
        if upgrade == 'коллектор':
            if clan.collect_bonus >= MAX_CLAN_BONUS:
                await update.message.reply_text("❌ Максимум 10")
                return
            cost = 25 + clan.collect_bonus * 5
            clan.collect_bonus += 1
        elif upgrade == 'опыт':
            if clan.exp_bonus >= MAX_CLAN_BONUS:
                await update.message.reply_text("❌ Максимум 10")
                return
            cost = 25 + clan.exp_bonus * 5
            clan.exp_bonus += 1
        elif upgrade == 'удвоение':
            if clan.double_bonus >= MAX_CLAN_BONUS:
                await update.message.reply_text("❌ Максимум 10")
                return
            cost = 25 + clan.double_bonus * 5
            clan.double_bonus += 1
        else:
            await update.message.reply_text("❌ коллектор/опыт/удвоение")
            return
        if clan.treasury_crystals < cost:
            await update.message.reply_text(f"❌ Нужно {cost} 💎")
            return
        clan.treasury_crystals -= cost
        session.commit()
        await update.message.reply_text(f"📈 *Улучшен {upgrade}!*", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in clan_upgrade: {e}")
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
            text += f"{i}. *{member.username or f'ID:{member.user_id}'}* — {role} — {member.level} уровень\n"
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

# ==================== РАДИО ====================

async def radion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Активация радио по коду"""
    if not context.args:
        await update.message.reply_text("❌ /radion [код]")
        return
    code = context.args[0]
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ /start")
            return
        if user.radio_active:
            await update.message.reply_text("❌ Радио уже активировано!")
            return
        if user.radio_code != code:
            await update.message.reply_text("❌ Неверный код!")
            return
        if user.radio_banned:
            await update.message.reply_text("❌ Вы заблокированы в радио!")
            return
        user.radio_active = True
        session.commit()
        await update.message.reply_text(
            "📻 *Радио активировано!*\n\n"
            "Теперь вы можете вещать командой:\n"
            "`/radio [текст]`\n\n"
            "📢 *Правила:*\n"
            "• Не чаще 1 раза в минуту\n"
            "• Не более 200 символов\n"
            "• Запрещены оскорбления и спам",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in radion: {e}")
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()

async def radio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить сообщение в радиоэфир"""
    if not context.args:
        await update.message.reply_text("❌ /radio [текст]")
        return
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ /start")
            return
        if not user.radio_active:
            await update.message.reply_text("❌ Радио не активировано! /radion [код]")
            return
        if user.radio_banned:
            await update.message.reply_text("❌ Вы заблокированы в радио!")
            return
        
        msg = ' '.join(context.args)
        if len(msg) > 200:
            await update.message.reply_text("❌ Не более 200 символов!")
            return
        
        last_radio = context.user_data.get('last_radio')
        if last_radio and datetime.now() - last_radio < timedelta(minutes=1):
            remaining = 60 - (datetime.now() - last_radio).seconds
            await update.message.reply_text(f"❌ Следующее сообщение через {remaining} секунд!")
            return
        
        context.user_data['last_radio'] = datetime.now()
        
        text = f"📻 *Радио Пустоши*\n\n🎙️ *Ведущий:* @{user.username}\n\n📢 {msg}"
        
        # Отправляем всем игрокам в личку
        users = session.query(User).all()
        sent = 0
        for u in users:
            try:
                await context.bot.send_message(chat_id=u.user_id, text=text, parse_mode='Markdown')
                sent += 1
            except:
                pass
        
        # Отправляем в группы, где есть бот (сохраняем ID групп в bot_data)
        groups = context.bot_data.get('radio_groups', set())
        for chat_id in groups:
            try:
                await context.bot.send_message(chat_id=chat_id, text=text, parse_mode='Markdown')
            except:
                pass
        
        await update.message.reply_text(
            f"✅ *Сообщение отправлено!*\n\n"
            f"📨 В личку: {sent}\n"
            f"👥 В группы: {len(groups)}\n"
            f"📻 Вещание завершено.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in radio: {e}")
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()

async def radio_register_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Регистрация группы для радио (вызывается при добавлении бота)"""
    if update.effective_chat.type in ['group', 'supergroup']:
        groups = context.bot_data.get('radio_groups', set())
        groups.add(update.effective_chat.id)
        context.bot_data['radio_groups'] = groups
        await update.message.reply_text("📻 *Радио Пустоши активировано в этой группе!*", parse_mode='Markdown')

# ==================== АДМИН-РАДИО ====================

async def aradio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ-панель радио"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    if len(context.args) < 1:
        await update.message.reply_text(
            "📻 *Админ-панель радио*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "/aradio give @ник [код] — выдать доступ\n"
            "/aradio take @ник — забрать доступ\n"
            "/aradio list — список ведущих\n"
            "/aradio ban @ник — заблокировать\n"
            "/aradio unban @ник — разблокировать",
            parse_mode='Markdown'
        )
        return
    
    action = context.args[0].lower()
    
    if action == 'give':
        if len(context.args) < 3:
            await update.message.reply_text("❌ /aradio give @ник [код]")
            return
        username = context.args[1].lstrip('@')
        code = context.args[2]
        session = Session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if not user:
                await update.message.reply_text(f"❌ @{username} не найден")
                return
            user.radio_code = code
            user.radio_active = False
            user.radio_banned = False
            session.commit()
            await update.message.reply_text(f"✅ Радиодоступ выдан @{username} с кодом `{code}`", parse_mode='Markdown')
            try:
                await context.bot.send_message(
                    user.user_id,
                    f"📻 *Вам выдан доступ к радио!*\n\n🔑 Код: `{code}`\n📝 Используйте: `/radion {code}`",
                    parse_mode='Markdown'
                )
            except:
                pass
        except Exception as e:
            logger.error(f"Error in aradio_give: {e}")
            await update.message.reply_text("❌ Ошибка")
        finally:
            Session.remove()
    
    elif action == 'take':
        if len(context.args) < 2:
            await update.message.reply_text("❌ /aradio take @ник")
            return
        username = context.args[1].lstrip('@')
        session = Session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if not user:
                await update.message.reply_text(f"❌ @{username} не найден")
                return
            user.radio_active = False
            user.radio_code = None
            session.commit()
            await update.message.reply_text(f"✅ Радиодоступ у @{username} забран", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in aradio_take: {e}")
            await update.message.reply_text("❌ Ошибка")
        finally:
            Session.remove()
    
    elif action == 'list':
        session = Session()
        try:
            users = session.query(User).filter(User.radio_active == True).all()
            if not users:
                await update.message.reply_text("📋 *Нет активных радиоведущих*", parse_mode='Markdown')
                return
            text = "📻 *Активные радиоведущие*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for i, u in enumerate(users, 1):
                status = "🔴 ЗАБАНЕН" if u.radio_banned else "🟢 АКТИВЕН"
                text += f"{i}. *{u.username or f'ID:{u.user_id}'}* — {status}\n"
            await update.message.reply_text(text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in aradio_list: {e}")
            await update.message.reply_text("❌ Ошибка")
        finally:
            Session.remove()
    
    elif action == 'ban':
        if len(context.args) < 2:
            await update.message.reply_text("❌ /aradio ban @ник")
            return
        username = context.args[1].lstrip('@')
        session = Session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if not user:
                await update.message.reply_text(f"❌ @{username} не найден")
                return
            user.radio_banned = True
            session.commit()
            await update.message.reply_text(f"✅ @{username} заблокирован в радио", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in aradio_ban: {e}")
            await update.message.reply_text("❌ Ошибка")
        finally:
            Session.remove()
    
    elif action == 'unban':
        if len(context.args) < 2:
            await update.message.reply_text("❌ /aradio unban @ник")
            return
        username = context.args[1].lstrip('@')
        session = Session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if not user:
                await update.message.reply_text(f"❌ @{username} не найден")
                return
            user.radio_banned = False
            session.commit()
            await update.message.reply_text(f"✅ @{username} разблокирован в радио", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in aradio_unban: {e}")
            await update.message.reply_text("❌ Ошибка")
        finally:
            Session.remove()
    
    else:
        await update.message.reply_text("❌ Используйте: give, take, list, ban, unban")
