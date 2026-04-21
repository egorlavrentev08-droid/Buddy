# admin.py - Админ-панель
# Версия: 2.0.0

# admin.py - Админ-панель
# Версия: 2.0.0

import json
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

# Импорты из config
from config import logger, MAX_LEVEL, get_exp_for_level, ADMIN_CODE, SUPER_ADMIN_IDS, CASINO_PUBLIC_CHANCE, CASINO_PUBLIC_CASH_MULT

# Импорты из core
from core import send_to_private, is_admin

# Импорты из database
from database import Session, User, Clan

# Импорты из utils
from utils import add_item_to_inventory, remove_item_from_inventory, get_item_count

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
    """Выдать ресурсы игроку"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    if len(context.args) < 3:
        await update.message.reply_text("❌ /give @ник [сумма] {RC,RF,RCr}")
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
        elif resource == 'RF':
            user.radfragments += amount
        elif resource == 'RCR':
            if user.clan_id:
                clan = session.query(Clan).filter_by(id=user.clan_id).first()
                if clan:
                    clan.treasury_crystals += amount
                    await update.message.reply_text(f"✅ *Выдано {amount} {resource} в казну клана {clan.name}!*", parse_mode='Markdown')
                else:
                    user.radcrystals += amount
                    await update.message.reply_text(f"✅ *Выдано {amount} {resource} лично @{username}*", parse_mode='Markdown')
            else:
                user.radcrystals += amount
                await update.message.reply_text(f"✅ *Выдано {amount} {resource} лично @{username}*", parse_mode='Markdown')
            session.commit()
            try:
                await context.bot.send_message(user.user_id, f"💰 *Вам выдали {amount} {resource}!*")
            except:
                pass
            return
        else:
            await update.message.reply_text("❌ RC, RF или RCr")
            return
        session.commit()
        await update.message.reply_text(f"✅ *Выдано {amount} {resource} @{username}*", parse_mode='Markdown')
        try:
            await context.bot.send_message(user.user_id, f"💰 *Вам выдали {amount} {resource}!*")
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
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return
    if level < 1 or level > MAX_LEVEL:
        await update.message.reply_text(f"❌ 1-{MAX_LEVEL}")
        return
    session = Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return
        old = user.level
        user.level = level
        user.experience = get_exp_for_level(level)
        session.commit()
        await update.message.reply_text(f"📈 *@{username}: {old} → {level}*", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in admin_setlevel: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== УПРАВЛЕНИЕ КУЛДАУНАМИ ====================

async def admin_cd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить кулдаун сбора"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ /cd @ник [минуты] (0=сброс)")
        return
    username = context.args[0].lstrip('@')
    try:
        minutes = int(context.args[1])
        if minutes < 0:
            await update.message.reply_text("❌ Неотрицательное число")
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
        if minutes == 0:
            user.next_collection_time = None
            await update.message.reply_text(f"✅ *Кулдаун @{username} сброшен*", parse_mode='Markdown')
        else:
            user.next_collection_time = datetime.now() + timedelta(minutes=minutes)
            await update.message.reply_text(f"⏰ *Кулдаун @{username} на {minutes} мин*", parse_mode='Markdown')
        session.commit()
    except Exception as e:
        logger.error(f"Error in admin_cd: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


async def admin_resethunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбросить кулдаун охоты"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    if len(context.args) < 1:
        await update.message.reply_text("❌ /resethunt @ник")
        return
    username = context.args[0].lstrip('@')
    session = Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return
        user.last_hunt = None
        session.commit()
        await update.message.reply_text(f"✅ *Кулдаун охоты @{username} сброшен*", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in admin_resethunt: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== УПРАВЛЕНИЕ ПРЕДМЕТАМИ ====================

async def admin_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдать или забрать предмет"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    if len(context.args) < 4:
        await update.message.reply_text("❌ /item give/take @ник [предмет] [кол-во]")
        return
    action = context.args[0].lower()
    username = context.args[1].lstrip('@')
    item = context.args[2].lower()
    try:
        count = int(context.args[3])
        if count <= 0:
            await update.message.reply_text("❌ Положительное число")
            return
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return
    
    valid_items = ['броня1', 'броня2', 'броня3', 'броня4', 'броня5',
                   'ружье', 'гарпун', 'винтовка', 'гаусс',
                   'аптечка', 'энергетик', 'редуктор']
    
    if item not in valid_items:
        await update.message.reply_text(f"❌ Неизвестный предмет. Доступны: {', '.join(valid_items)}")
        return
    
    session = Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return
        
        if action == 'give':
            add_item_to_inventory(user, item, count)
            session.commit()
            await update.message.reply_text(f"✅ *Выдано {item} x{count} @{username}*", parse_mode='Markdown')
            try:
                await context.bot.send_message(user.user_id, f"📦 *Вам выдали {item} x{count}!*")
            except:
                pass
        elif action == 'take':
            available = get_item_count(user, item)
            if available < count:
                await update.message.reply_text(f"❌ У @{username} только {available} шт {item}")
                return
            remove_item_from_inventory(user, item, count)
            session.commit()
            await update.message.reply_text(f"✅ *Забрано {item} x{count} у @{username}*", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ give или take")
    except Exception as e:
        logger.error(f"Error in admin_item: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


async def admin_pets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление питомцами"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    if len(context.args) < 3:
        await update.message.reply_text("❌ /pets give/take @ник [питомец]")
        return
    action = context.args[0].lower()
    username = context.args[1].lstrip('@')
    session = Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            await update.message.reply_text(f"❌ @{username} не найден")
            return
        valid_pets = ['овчарка', 'волк', 'рысь', 'пума', 'попугай', 'кайот']
        if action == 'give':
            pet_name = context.args[2].lower()
            if pet_name not in valid_pets:
                await update.message.reply_text(f"❌ Доступны: {', '.join(valid_pets)}")
                return
            user.pet = pet_name
            session.commit()
            await update.message.reply_text(f"🐾 *Выдан питомец {pet_name} @{username}*", parse_mode='Markdown')
            try:
                await context.bot.send_message(user.user_id, f"🐾 *Вам выдали питомца {pet_name}!*")
            except:
                pass
        elif action == 'take':
            if not user.pet:
                await update.message.reply_text(f"❌ У @{username} нет питомца")
                return
            user.pet = None
            session.commit()
            await update.message.reply_text(f"🐾 *Забран питомец у @{username}*", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ give или take")
    except Exception as e:
        logger.error(f"Error in admin_pets: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== УПРАВЛЕНИЕ АДМИНАМИ ====================

async def admin_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление администраторами (только главный админ)"""
    if update.effective_user.id not in SUPER_ADMIN_IDS:
        await update.message.reply_text("❌ Только главный администратор!")
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "👑 *Управление админами*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "/admin add @ник — добавить админа\n"
            "/admin remove @ник — удалить админа\n"
            "/admin block @ник — заблокировать\n"
            "/admin unblock @ник — разблокировать\n"
            "/admin list — список админов",
            parse_mode='Markdown'
        )
        return
    action = context.args[0].lower()
    username = context.args[1].lstrip('@')
    session = Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            await update.message.reply_text(f"❌ @{username} не найден")
            return
        if action == 'add':
            if user.is_admin:
                await update.message.reply_text("❌ Уже админ")
                return
            user.is_admin = True
            user.is_blocked = False
            session.commit()
            await update.message.reply_text(f"✅ *@{username} добавлен в админы*", parse_mode='Markdown')
            try:
                await context.bot.send_message(user.user_id, "👑 *Вы назначены администратором Пустоши!*")
            except:
                pass
        elif action == 'remove':
            if not user.is_admin:
                await update.message.reply_text("❌ Не админ")
                return
            user.is_admin = False
            user.is_blocked = False
            session.commit()
            await update.message.reply_text(f"✅ *@{username} удалён из админов*", parse_mode='Markdown')
        elif action == 'block':
            if not user.is_admin:
                await update.message.reply_text("❌ Не админ")
                return
            if user.user_id in SUPER_ADMIN_IDS:
                await update.message.reply_text("❌ Нельзя заблокировать главного админа")
                return
            user.is_blocked = True
            session.commit()
            await update.message.reply_text(f"✅ *@{username} заблокирован*", parse_mode='Markdown')
        elif action == 'unblock':
            if not user.is_admin:
                await update.message.reply_text("❌ Не админ")
                return
            user.is_blocked = False
            session.commit()
            await update.message.reply_text(f"✅ *@{username} разблокирован*", parse_mode='Markdown')
        elif action == 'list':
            admins = session.query(User).filter(User.is_admin == True).all()
            if not admins:
                await update.message.reply_text("📋 *Нет админов*", parse_mode='Markdown')
                return
            text = "👑 *Список администраторов*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for i, a in enumerate(admins, 1):
                status = "🔴" if a.is_blocked else "🟢"
                main = " (ГЛАВНЫЙ)" if a.user_id in SUPER_ADMIN_IDS else ""
                text += f"{i}. {status} *{a.username or f'ID:{a.user_id}'}*{main}\n"
            await update.message.reply_text(text, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ add/remove/block/unblock/list")
    except Exception as e:
        logger.error(f"Error in admin_manage: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


async def admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список администраторов (для всех)"""
    session = Session()
    try:
        admins_list = session.query(User).filter(User.is_admin == True).all()
        if not admins_list:
            await update.message.reply_text("📋 *Нет администраторов*", parse_mode='Markdown')
            return
        text = "👑 *Администраторы Пустоши*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, a in enumerate(admins_list, 1):
            status = "🔴" if a.is_blocked else "🟢"
            main = " (ГЛАВНЫЙ)" if a.user_id in SUPER_ADMIN_IDS else ""
            text += f"{i}. {status} *{a.username or f'ID:{a.user_id}'}*{main}\n"
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in admins: {e}")
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== УПРАВЛЕНИЕ КЛАССАМИ ====================

async def admin_classes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сменить класс игроку (админ)"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    if len(context.args) < 3 or context.args[0].lower() != 'set':
        await update.message.reply_text(
            "👑 *Смена класса (админ)*\n\n"
            "/classes set @ник [класс]\n\n"
            "Доступные классы:\n"
            "• сталкер — базовый\n"
            "• военный — +30% опыт, +20% RC, -30% RF\n"
            "• бандит — +40% RF, +15% RC, -25% опыт\n"
            "• ученый — +50% опыт, +25% RF, -20% RC",
            parse_mode='Markdown'
        )
        return
    username = context.args[1].lstrip('@')
    class_name = context.args[2].lower()
    valid_classes = {'сталкер': 'stalker', 'военный': 'military', 'бандит': 'bandit', 'ученый': 'scientist'}
    if class_name not in valid_classes:
        await update.message.reply_text("❌ Доступные классы: сталкер, военный, бандит, ученый")
        return
    session = Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            await update.message.reply_text(f"❌ @{username} не найден")
            return
        old_class = user.user_class if hasattr(user, 'user_class') else 'stalker'
        user.user_class = valid_classes[class_name]
        user.last_free_class_change = datetime.now()
        session.commit()
        class_emoji = {'stalker': '🟢', 'military': '🔫', 'bandit': '🗡️', 'scientist': '🔬'}
        await update.message.reply_text(
            f"✅ *Класс @{username} изменён!*\n\n"
            f"🎭 {class_emoji.get(old_class, '🟢')} {old_class} → {class_emoji.get(valid_classes[class_name], '🟢')} {class_name}",
            parse_mode='Markdown'
        )
        try:
            await context.bot.send_message(
                user.user_id,
                f"👑 *Администратор изменил ваш класс на {class_name}!*"
            )
        except:
            pass
    except Exception as e:
        logger.error(f"Error in admin_classes: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== УПРАВЛЕНИЕ СУНДУКАМИ ====================

async def gchest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдать сундуки игроку"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ /gchest @ник [тип] [кол-во]\n\nТипы: common, rare, epic, mythic, legendary")
        return
    username = context.args[0].lstrip('@')
    chest_type = context.args[1].lower()
    count = 1
    if len(context.args) > 2:
        try:
            count = int(context.args[2])
            if count <= 0 or count > 100:
                await update.message.reply_text("❌ 1-100")
                return
        except ValueError:
            await update.message.reply_text("❌ Введите число")
            return
    session = Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            await update.message.reply_text(f"❌ @{username} не найден")
            return
        emoji = ""
        if chest_type == 'common':
            user.chest_common += count
            emoji = "🟢"
        elif chest_type == 'rare':
            user.chest_rare += count
            emoji = "🔵"
        elif chest_type == 'epic':
            user.chest_epic += count
            emoji = "🟣"
        elif chest_type == 'mythic':
            user.chest_mythic += count
            emoji = "🟡"
        elif chest_type == 'legendary':
            user.chest_legendary += count
            emoji = "🟠"
        else:
            await update.message.reply_text("❌ Тип: common, rare, epic, mythic, legendary")
            return
        session.commit()
        await update.message.reply_text(f"✅ *Выдано {count} {emoji} {chest_type} сундуков @{username}*", parse_mode='Markdown')
        try:
            await context.bot.send_message(user.user_id, f"🎁 *Вам выдали {count} {chest_type} сундуков!*")
        except:
            pass
    except Exception as e:
        logger.error(f"Error in gchest: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== РАССЫЛКИ ====================

async def call(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Массовая рассылка всем игрокам"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    if not context.args:
        await update.message.reply_text("❌ /call [текст]")
        return
    msg = ' '.join(context.args)
    admin = update.effective_user.first_name
    session = Session()
    try:
        users = session.query(User).all()
        sent = 0
        for u in users:
            try:
                await context.bot.send_message(u.user_id, f"📢 *Объявление от администратора*\n\n{msg}\n\n👑 {admin}", parse_mode='Markdown')
                sent += 1
            except:
                pass
        await update.message.reply_text(f"✅ *Рассылка завершена!*\n📨 Отправлено: {sent}", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in call: {e}")
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


async def lscall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Личная рассылка игроку"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ /lscall @ник [текст]")
        return
    username = context.args[0].lstrip('@')
    msg = ' '.join(context.args[1:])
    admin = update.effective_user.first_name
    session = Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            await update.message.reply_text(f"❌ @{username} не найден")
            return
        await context.bot.send_message(user.user_id, f"📨 *Личное сообщение от администратора*\n\n{msg}\n\n👑 {admin}", parse_mode='Markdown')
        await update.message.reply_text(f"✅ *Сообщение отправлено @{username}*", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in lscall: {e}")
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== УПРАВЛЕНИЕ ВИДИМОСТЬЮ В ТОПАХ ====================

async def admin_hide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скрыть/показать игрока в топах"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ /hide @ник — скрыть из топов\n/show @ник — показать")
        return
    action = context.args[0].lower()
    username = context.args[1].lstrip('@')
    session = Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return
        if action == 'hide':
            user.is_admin_visible = False
            session.commit()
            await update.message.reply_text(f"✅ *@{username} скрыт из топов*", parse_mode='Markdown')
        elif action == 'show':
            user.is_admin_visible = True
            session.commit()
            await update.message.reply_text(f"✅ *@{username} виден в топах*", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Используйте hide или show")
    except Exception as e:
        logger.error(f"Error in admin_hide: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== ТАБЛИЦА ЛИДЕРОВ ====================

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Таблица лидеров"""
    if not context.args:
        await update.message.reply_text(
            "🏆 *Таблица лидеров*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "/top level — по уровню\n"
            "/top rc — по РадКоинами\n"
            "/top boss — по убитым Боссам\n"
            "/top hunt — по мутантам\n"
            "/top clan — по кланам",
            parse_mode='Markdown'
        )
        return
    cat = context.args[0].lower()
    session = Session()
    try:
        if cat == 'level':
            users = session.query(User).filter(User.is_admin_visible == True).order_by(User.level.desc()).limit(10).all()
            title = "🏆 *Топ-10 по уровню*"
            val = lambda u: u.level
        elif cat == 'rc':
            users = session.query(User).filter(User.is_admin_visible == True).order_by(User.radcoins.desc()).limit(10).all()
            title = "💰 *Топ-10 по РадКоинами*"
            val = lambda u: f"{u.radcoins:.0f}"
        elif cat == 'boss':
            users = session.query(User).filter(User.is_admin_visible == True).order_by(User.bosses_killed.desc()).limit(10).all()
            title = "👑 *Топ-10 по Боссам*"
            val = lambda u: u.bosses_killed
        elif cat == 'hunt':
            users = session.query(User).filter(User.is_admin_visible == True).order_by(User.mutants_killed.desc()).limit(10).all()
            title = "🧬 *Топ-10 по мутантам*"
            val = lambda u: u.mutants_killed
        elif cat == 'clan':
            clans = session.query(Clan).all()
            stats = [(c.name, session.query(User).filter_by(clan_id=c.id).count()) for c in clans]
            stats.sort(key=lambda x: x[1], reverse=True)
            text = "🏰 *Топ-10 кланов*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for i, (n, c) in enumerate(stats[:10], 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                text += f"{medal} *{n}* — 👥 {c}\n"
            await update.message.reply_text(text, parse_mode='Markdown')
            return
        else:
            await update.message.reply_text("❌ Используйте: level, rc, boss, hunt, clan")
            return
        
        if not users:
            await update.message.reply_text("📋 *Нет игроков*", parse_mode='Markdown')
            return
        
        text = f"{title}\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, u in enumerate(users, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} *{u.username or f'ID:{u.user_id}'}* — {val(u)}\n"
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in top: {e}")
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== ФАЗЫ ПУСТОШИ ====================

async def admin_phase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Смена фазы Пустоши"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    if not context.args:
        await update.message.reply_text("❌ /phase 1/2/3")
        return
    try:
        phase = int(context.args[0])
        if phase not in [1, 2, 3]:
            await update.message.reply_text("❌ 1, 2 или 3")
            return
        context.bot_data['phase'] = phase
        phases = {1: "🟢 Мирная", 2: "🟡 Опасная", 3: "🔴 Апокалиптическая"}
        await update.message.reply_text(f"🌍 *Фаза изменена на {phases[phase]}*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ Введите число")


# ==================== НАСТРОЙКА КАЗИНО (ТОЛЬКО ГЛАВНЫЙ АДМИН) ====================

async def acasino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройка казино (только главный админ)"""
    if update.effective_user.id not in SUPER_ADMIN_IDS:
        await update.message.reply_text("❌ Только главный администратор!")
        return
    
    if len(context.args) < 3:
        await update.message.reply_text(
            "🎰 *Настройка казино*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "/acasino public chance [1-100] — публичный шанс\n"
            "/acasino public cash [1-1000] — публичный множитель\n"
            "/acasino private @username chance [1-100] — личный шанс\n"
            "/acasino private @username cash [1-1000] — личный множитель\n"
            "/acasino reset @username — сбросить личные настройки\n"
            "/acasino stats @username — посмотреть настройки",
            parse_mode='Markdown'
        )
        return
    
    action = context.args[0].lower()
    
    if action == 'public':
        if len(context.args) < 3:
            await update.message.reply_text("❌ /acasino public [chance/cash] [значение]")
            return
        setting = context.args[1].lower()
        try:
            value = int(context.args[2])
        except ValueError:
            await update.message.reply_text("❌ Введите число")
            return
        
        if setting == 'chance':
            if value < 1 or value > 100:
                await update.message.reply_text("❌ Шанс от 1 до 100")
                return
            context.bot_data['casino_public_chance'] = value
            await update.message.reply_text(f"✅ *Публичный шанс казино: {value}%*", parse_mode='Markdown')
        elif setting == 'cash':
            if value < 1 or value > 1000:
                await update.message.reply_text("❌ Множитель от 1 до 1000")
                return
            context.bot_data['casino_public_cash_mult'] = value
            await update.message.reply_text(f"✅ *Публичный множитель казино: x{value}*", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ chance или cash")
    
    elif action == 'private':
        if len(context.args) < 4:
            await update.message.reply_text("❌ /acasino private @username [chance/cash] [значение]")
            return
        username = context.args[1].lstrip('@')
        setting = context.args[2].lower()
        try:
            value = int(context.args[3])
        except ValueError:
            await update.message.reply_text("❌ Введите число")
            return
        
        session = Session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if not user:
                await update.message.reply_text(f"❌ @{username} не найден")
                return
            
            if setting == 'chance':
                if value < 1 or value > 100:
                    await update.message.reply_text("❌ Шанс от 1 до 100")
                    return
                user.casino_chance = value
                session.commit()
                await update.message.reply_text(f"✅ *Личный шанс @{username}: {value}%*", parse_mode='Markdown')
            elif setting == 'cash':
                if value < 1 or value > 1000:
                    await update.message.reply_text("❌ Множитель от 1 до 1000")
                    return
                user.casino_cash_mult = value
                session.commit()
                await update.message.reply_text(f"✅ *Личный множитель @{username}: x{value}*", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ chance или cash")
        except Exception as e:
            logger.error(f"Error in acasino private: {e}")
            session.rollback()
            await update.message.reply_text("❌ Ошибка")
        finally:
            Session.remove()
    
    elif action == 'reset':
        if len(context.args) < 2:
            await update.message.reply_text("❌ /acasino reset @username")
            return
        username = context.args[1].lstrip('@')
        session = Session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if not user:
                await update.message.reply_text(f"❌ @{username} не найден")
                return
            user.casino_chance = None
            user.casino_cash_mult = None
            session.commit()
            await update.message.reply_text(f"✅ *Личные настройки казино @{username} сброшены*", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in acasino reset: {e}")
            session.rollback()
            await update.message.reply_text("❌ Ошибка")
        finally:
            Session.remove()
    
    elif action == 'stats':
        if len(context.args) < 2:
            await update.message.reply_text("❌ /acasino stats @username")
            return
        username = context.args[1].lstrip('@')
        session = Session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if not user:
                await update.message.reply_text(f"❌ @{username} не найден")
                return
            
            pub_chance = context.bot_data.get('casino_public_chance', CASINO_PUBLIC_CHANCE)
            pub_mult = context.bot_data.get('casino_public_cash_mult', CASINO_PUBLIC_CASH_MULT)
            priv_chance = user.casino_chance if user.casino_chance is not None else "не задан"
            priv_mult = user.casino_cash_mult if user.casino_cash_mult is not None else "не задан"
            
            text = (
                f"🎰 *Настройки казино @{username}*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 *Публичные:*\n"
                f"   • Шанс: {pub_chance}%\n"
                f"   • Множитель: x{pub_mult}\n\n"
                f"🔒 *Личные:*\n"
                f"   • Шанс: {priv_chance}\n"
                f"   • Множитель: {priv_mult}"
            )
            await update.message.reply_text(text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in acasino stats: {e}")
            await update.message.reply_text("❌ Ошибка")
        finally:
            Session.remove()
    
    else:
        await update.message.reply_text("❌ Используйте: public, private, reset, stats")


# ==================== СОВЕТЫ ====================

async def advice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Советы Старого сталкера"""
    text = (
        "📖 *Советы Старого сталкера*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Напиши `/advice` и слово:\n\n"
        "🎲 `сбор` — как добывать ресурсы\n"
        "🏹 `охота` — как охотиться на мутантов\n"
        "🛒 `магазин` — что и зачем покупать\n"
        "🛠️ `крафт` — что можно создать\n"
        "💱 `обмен` — как менять фрагменты\n"
        "🎰 `казино` — как испытать удачу\n"
        "🐾 `питомцы` — как найти друга\n"
        "🏰 `кланы` — как создать и развивать\n"
        "🌪️ `аномалии` — что случается в Пустоши\n"
        "🔔 `уведомления` — как не пропустить\n"
        "🎭 `классы` — система классов\n"
        "🗺️ `локации` — все локации\n"
        "🎁 `сундуки` — типы сундуков\n\n"
        "Пример: `/advice охота`"
    )
    await send_to_private(update, context, text)


async def advice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик советов"""
    if not context.args:
        await advice(update, context)
        return
    topic = context.args[0].lower()
    tips = {
        'сбор': "🎲 *СБОР РЕСУРСОВ*\n\n/collect — 30-120 мин. Находка: RC, опыт, RF.",
        'охота': "🏹 *ОХОТА НА МУТАНТОВ*\n\n/hunt — раз в сутки. Шансы зависят от оружия.",
        'магазин': "🛒 *МАГАЗИН ПУСТОШИ*\n\n/shop — все цены. /buy [товар] [кол-во]",
        'крафт': "🛠️ *КРАФТ ПРЕДМЕТОВ*\n\n/craft [предмет]. Аптечка — 2 RF",
        'обмен': "💱 *ОБМЕН ФРАГМЕНТОВ*\n\n/exchange [количество]. 1RF=50RC",
        'казино': "🎰 *КАЗИНО*\n\n/casino [сумма]. Ставка от 100 до 100000 RC",
        'питомцы': "🐾 *ПИТОМЦЫ*\n\nПри сборе 0.5% шанс встретить. /pet accept — приручить",
        'кланы': "🏰 *КЛАНЫ*\n\n/clan create [название] (2ур,1000RC)",
        'аномалии': "🌪️ *АНОМАЛИИ* (3 фаза)\n\nДобытчик(+30%RC), Ловец(риск 90%)",
        'уведомления': "🔔 *УВЕДОМЛЕНИЯ*\n\n/announce on — включить",
        'классы': "🎭 *КЛАССЫ*\n\n/class [сталкер/военный/бандит/ученый]",
        'локации': "🗺️ *ЛОКАЦИИ*\n\n/locate [normal/military/city/wasteland/lab/forest/market]",
        'сундуки': "🎁 *СУНДУКИ*\n\n/chest open [common/rare/epic/mythic/legendary]"
    }
    await send_to_private(update, context, tips.get(topic, "❌ Неизвестный раздел. Используйте /advice"))


# ==================== СПИСОК ИГРОКОВ (АДМИН) ====================

async def admin_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список всех игроков (админ)"""
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
            text += f"{i}. *{u.username or f'ID:{u.user_id}'}* — ур.{u.level}, RC:{u.radcoins:.0f}, 🏰{clan_name}\n"
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

# ==================== РАСПРОДАЖИ ====================

async def sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устроить распродажу в магазине (админ)"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "🏷️ *Распродажа*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "/sale [скидка%] [часы] — устроить распродажу\n"
            "/sale end — завершить распродажу\n\n"
            "Пример: `/sale 50 24` — скидка 50% на 24 часа",
            parse_mode='Markdown'
        )
        return
    
    if context.args[0].lower() == 'end':
        context.bot_data['sale_discount'] = 0
        context.bot_data['sale_until'] = None
        await update.message.reply_text("✅ *Распродажа завершена!* Цены вернулись к обычным.", parse_mode='Markdown')
        return
    
    try:
        discount = int(context.args[0])
        hours = int(context.args[1])
        
        if discount < 1 or discount > 90:
            await update.message.reply_text("❌ Скидка от 1% до 90%")
            return
        if hours < 1 or hours > 168:
            await update.message.reply_text("❌ Время от 1 до 168 часов")
            return
        
        context.bot_data['sale_discount'] = discount
        context.bot_data['sale_until'] = datetime.now() + timedelta(hours=hours)
        
        await update.message.reply_text(
            f"🏷️ *РАСПРОДАЖА!*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎉 Скидка {discount}% на ВСЕ товары!\n"
            f"⏰ Длительность: {hours} часов\n"
            f"📅 До: {(datetime.now() + timedelta(hours=hours)).strftime('%d.%m %H:%M')}\n\n"
            f"🛒 Торопитесь, предложение ограничено!",
            parse_mode='Markdown'
        )
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Пример: `/sale 50 24`", parse_mode='Markdown')
        
