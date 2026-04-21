# money.py - Экономика и магазин
# Версия: 2.0.0

import random
import json
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from config import logger, MAX_MEDKITS, CASINO_PUBLIC_CHANCE, CASINO_PUBLIC_CASH_MULT, CASINO_MIN_BET, CASINO_MAX_BET, SHOP_LIMITS, SHOP_RESET_HOURS
from core import send_to_private
from database import Session, User
from utils import get_inventory, get_equipped, get_item_count, add_item_to_inventory, remove_item_from_inventory, check_achievements, save_equipped


# ==================== ОБЩИЕ ЛИМИТЫ ====================

def check_global_shop_limit(item, count, context):
    """Проверка общих лимитов магазина"""
    if item not in SHOP_LIMITS:
        return True, None
    
    now = datetime.now()
    last_reset = context.bot_data.get('last_shop_reset')
    limits = context.bot_data.get('shop_limits', {})
    
    if last_reset and now - last_reset > timedelta(hours=SHOP_RESET_HOURS):
        context.bot_data['shop_limits'] = SHOP_LIMITS.copy()
        context.bot_data['last_shop_reset'] = now
        limits = context.bot_data['shop_limits']
    
    available = limits.get(item, 0)
    
    if count > available:
        next_reset = last_reset + timedelta(hours=SHOP_RESET_HOURS) if last_reset else now + timedelta(hours=SHOP_RESET_HOURS)
        remaining = next_reset - now
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60
        return False, f"❌ Лимит на {item}: осталось {available} шт. Поставка через {hours}ч {minutes}мин"
    
    return True, None


def apply_global_shop_limit(item, count, context):
    """Списать товар из общих лимитов"""
    limits = context.bot_data.get('shop_limits', {})
    if item in limits:
        limits[item] -= count
        context.bot_data['shop_limits'] = limits


# ==================== ИНВЕНТАРЬ ====================

async def inv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать инвентарь и экипировку"""
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ /start")
            return
        
        inventory = get_inventory(user)
        equipped = get_equipped(user)
        
        text = "📦 *Инвентарь*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        text += "*🟢 ЭКИПИРОВАНО*\n"
        armor_display = {
            'броня1': '🟢 Лёгкая броня (25%)',
            'броня2': '🔵 Утяжеленная броня (40%)',
            'броня3': '🟣 Тактическая броня (50%)',
            'броня4': '🟠 Тяжёлая броня (60%)',
            'броня5': '🔴 Силовая броня (75%)'
        }
        if equipped.get('armor'):
            text += f"{armor_display.get(equipped['armor'], equipped['armor'])} — активна\n"
        
        weapon_display = {
            'ружье': '🔫 Ружьё',
            'гарпун': '🎣 Гарпун',
            'винтовка': '🔫 Винтовка',
            'гаусс': '⚡ Винтовка Гаусса'
        }
        if equipped.get('weapon'):
            text += f"{weapon_display.get(equipped['weapon'], equipped['weapon'])} — экипировано\n"
        
        if not any([equipped.get('armor'), equipped.get('weapon')]):
            text += "❌ Нет экипированных предметов\n"
        
        text += "\n*📦 ПРЕДМЕТЫ*\n"
        inventory.sort(key=lambda x: x['item'])
        
        item_names = {
            'броня1': '🟢 Лёгкая броня', 'броня2': '🔵 Утяжеленная броня',
            'броня3': '🟣 Тактическая броня', 'броня4': '🟠 Тяжёлая броня',
            'броня5': '🔴 Силовая броня', 'ружье': '🔫 Ружьё',
            'гарпун': '🎣 Гарпун', 'винтовка': '🔫 Винтовка',
            'гаусс': '⚡ Винтовка Гаусса', 'аптечка': '💊 Аптечка',
            'энергетик': '⚡ Энергетик', 'редуктор': '⏱️ Редуктор'
        }
        
        for item in inventory:
            name = item['item']
            count = item['count']
            display_name = item_names.get(name, name)
            expires = item.get('expires')
            if expires:
                exp_date = datetime.fromisoformat(expires)
                if exp_date > datetime.now():
                    text += f"{display_name} — {count} шт (до {exp_date.strftime('%d.%m %H:%M')})\n"
            else:
                text += f"{display_name} — {count} шт\n"
        
        if not inventory:
            text += "❌ Инвентарь пуст\n"
        
        text += "\n*⚡ АКТИВНЫЕ ЭФФЕКТЫ*\n"
        now = datetime.now()
        
        if user.energy_drink_until and user.energy_drink_until > now:
            remaining = user.energy_drink_until - now
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            text += f"⚡ Энергетик — {hours}ч {minutes}мин (стеков: {user.energy_drink_stacks})\n"
        else:
            text += "⚡ Энергетик — не активен\n"
        
        if user.cooldown_reducer_until and user.cooldown_reducer_until > now:
            remaining = user.cooldown_reducer_until - now
            days = remaining.days
            hours = remaining.seconds // 3600
            text += f"⏱️ Редуктор — {days}д {hours}ч (стеков: {user.reducer_stacks})\n"
        else:
            text += "⏱️ Редуктор — не активен\n"
        
        text += "\n💡 Команды:\n/sell [предмет] [кол-во]\n/equip броня/оружие [название]\n/equip броня/оружие 0 — снять\n/use энергетик/редуктор [кол-во]"
        
        await send_to_private(update, context, text)
    except Exception as e:
        logger.error(f"Error in inv: {e}")
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== МАГАЗИН ====================

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать магазин (только доступные товары)"""
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ /start")
            return
        
        now = datetime.now()
        discount = context.bot_data.get('sale_discount', 0)
        sale_until = context.bot_data.get('sale_until')
        
        sale_line = ""
        if discount > 0 and sale_until and sale_until > now:
            remaining = sale_until - now
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            sale_line = f"\n\n🔥 *РАСПРОДАЖА {discount}%!* {hours}ч {minutes}мин 🔥"
        
        text = f"🛒 *Магазин Пустоши*{sale_line}\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        text += "*🛡️ БРОНЯ*\n"
        if user.level >= 1:
            text += "• 🟢 Лёгкая броня (1000) — 25%\n"
        if user.level >= 10:
            text += "• 🔵 Утяжеленная броня (2500) — 40%\n"
        if user.level >= 1:
            text += "• 🟣 Тактическая броня (5000) — 50%\n"
        if user.level >= 25:
            text += "• 🟠 Тяжёлая броня (10000) — 60%\n"
        if user.level >= 50:
            text += "• 🔴 Силовая броня (25000) — 75%\n"
        text += "\n"
        
        text += "*⚔️ ОРУЖИЕ*\n"
        if user.level >= 1:
            text += "• 🔫 Ружьё (300)\n"
        if user.level >= 10:
            text += "• 🎣 Гарпун (500)\n"
        if user.level >= 25:
            text += "• 🔫 Винтовка (5000)\n"
        if user.level >= 50:
            text += "• ⚡ Винтовка Гаусса (20000)\n"
        text += "\n"
        
        text += "*💊 РАСХОДНИКИ*\n"
        text += "• 💊 Аптечка (125)\n"
        text += "• ⚡ Энергетик (250)\n"
        text += "• ⏱️ Редуктор (1250)\n\n"
        
        limits = context.bot_data.get('shop_limits', {})
        text += "*📦 ОСТАТКИ*\n"
        
        if user.level >= 1:
            text += f"• Тактическая броня ({limits.get('броня3', 10)}/10)\n"
        if user.level >= 25:
            text += f"• Тяжёлая броня ({limits.get('броня4', 7)}/7)\n"
        if user.level >= 50:
            text += f"• Силовая броня ({limits.get('броня5', 5)}/5)\n"
        if user.level >= 25:
            text += f"• Винтовка ({limits.get('винтовка', 7)}/7)\n"
        if user.level >= 50:
            text += f"• Гаусс ({limits.get('гаусс', 5)}/5)\n"
        
        text += f"• Аптечка ({limits.get('аптечка', 75)}/75)\n"
        text += f"• Редуктор ({limits.get('редуктор', 30)}/30)\n"
        text += f"• Энергетик ({limits.get('энергетик', 15)}/15)\n\n"
        
        last_reset = context.bot_data.get('last_shop_reset')
        if last_reset:
            next_reset = last_reset + timedelta(hours=SHOP_RESET_HOURS)
            if next_reset > now:
                remaining = next_reset - now
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                text += f"🔄 Поставка через: {hours}ч {minutes}мин\n"
            else:
                text += "🔄 Новая поставка уже доступна!\n"
        
        text += "\n📝 */buy [товар] [кол-во]*"
        
        await send_to_private(update, context, text)
    except Exception as e:
        logger.error(f"Error in shop: {e}")
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== ПОКУПКА ====================

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Купить предмет"""
    if not context.args:
        await update.message.reply_text("❌ /buy [товар] [кол-во]")
        return
    
    item = context.args[0].lower()
    count = 1
    if len(context.args) > 1:
        try:
            count = int(context.args[1])
            if count <= 0 or count > 100:
                await update.message.reply_text("❌ 1-100 штук за раз")
                return
        except ValueError:
            await update.message.reply_text("❌ Введите число")
            return
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ /start")
            return
        
        prices = {
            'аптечка': 125, 'энергетик': 250, 'редуктор': 1250,
            'ружье': 300, 'гарпун': 500, 'винтовка': 5000, 'гаусс': 20000,
            'броня1': 1000, 'броня2': 2500, 'броня3': 5000,
            'броня4': 10000, 'броня5': 25000
        }
        
        if item not in prices:
            await update.message.reply_text(f"❌ Товар '{item}' не найден")
            return
        
        # Проверка уровня
        if item == 'гарпун' and user.level < 10:
            await update.message.reply_text("❌ Гарпун доступен с 10 уровня!")
            return
        if item == 'винтовка' and user.level < 25:
            await update.message.reply_text("❌ Винтовка доступна с 25 уровня!")
            return
        if item == 'гаусс' and user.level < 50:
            await update.message.reply_text("❌ Винтовка Гаусса доступна с 50 уровня!")
            return
        if item == 'броня2' and user.level < 10:
            await update.message.reply_text("❌ Утяжеленная броня доступна с 10 уровня!")
            return
        if item == 'броня4' and user.level < 25:
            await update.message.reply_text("❌ Тяжёлая броня доступна с 25 уровня!")
            return
        if item == 'броня5' and user.level < 50:
            await update.message.reply_text("❌ Силовая броня доступна с 50 уровня!")
            return
        
        # Проверка лимита
        can_buy, limit_msg = check_global_shop_limit(item, count, context)
        if not can_buy:
            await update.message.reply_text(limit_msg, parse_mode='Markdown')
            return
        
        # Расчёт стоимости со скидкой
        total = prices[item] * count
        now = datetime.now()
        discount = context.bot_data.get('sale_discount', 0)
        sale_until = context.bot_data.get('sale_until')
        
        if discount > 0 and sale_until and sale_until > now:
            old_total = total
            total = int(total * (100 - discount) / 100)
            discount_msg = f"\n🏷️ Скидка {discount}%: {old_total} → {total} RC!"
        else:
            discount_msg = ""
        
        if user.radcoins < total:
            await update.message.reply_text(f"❌ Нужно {total} RC, у вас {user.radcoins:.0f}")
            return
        
        user.radcoins -= total
        
        # Выдача предмета
        if item == 'ружье':
            add_item_to_inventory(user, 'ружье', count)
        elif item == 'гарпун':
            add_item_to_inventory(user, 'гарпун', count)
        elif item == 'винтовка':
            add_item_to_inventory(user, 'винтовка', count)
        elif item == 'гаусс':
            add_item_to_inventory(user, 'гаусс', count)
        elif item == 'аптечка':
            add_item_to_inventory(user, 'аптечка', count)
        elif item == 'энергетик':
            add_item_to_inventory(user, 'энергетик', count)
        elif item == 'редуктор':
            add_item_to_inventory(user, 'редуктор', count)
        elif item == 'броня1':
            add_item_to_inventory(user, 'броня1', count)
        elif item == 'броня2':
            add_item_to_inventory(user, 'броня2', count)
        elif item == 'броня3':
            add_item_to_inventory(user, 'броня3', count)
        elif item == 'броня4':
            add_item_to_inventory(user, 'броня4', count)
        elif item == 'броня5':
            add_item_to_inventory(user, 'броня5', count)
        
        # Списание из общих лимитов
        apply_global_shop_limit(item, count, context)
        
        user.total_purchases += count
        check_achievements(user, session)
        session.commit()
        
        item_names = {
            'аптечка': '💊 Аптечка', 'энергетик': '⚡ Энергетик', 'редуктор': '⏱️ Редуктор',
            'ружье': '🔫 Ружьё', 'гарпун': '🎣 Гарпун', 'винтовка': '🔫 Винтовка', 'гаусс': '⚡ Винтовка Гаусса',
            'броня1': '🟢 Лёгкая броня', 'броня2': '🔵 Утяжеленная броня', 'броня3': '🟣 Тактическая броня',
            'броня4': '🟠 Тяжёлая броня', 'броня5': '🔴 Силовая броня'
        }
        
        msg = f"✅ *Куплено {item_names.get(item, item)} x{count}*\n💰 -{total} RC{discount_msg}\n☢️ Осталось: {user.radcoins:.0f} RC"
        
        # Показываем остаток лимита
        if item in SHOP_LIMITS:
            limits = context.bot_data.get('shop_limits', {})
            available = limits.get(item, 0)
            total_limit = SHOP_LIMITS[item]
            msg += f"\n📦 Осталось на складе: {available}/{total_limit}"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in buy: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== ПРОДАЖА ====================

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Продать предмет"""
    if not context.args:
        await update.message.reply_text(
            "💰 *Продажа предметов*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "/sell [предмет] — продать 1 шт\n"
            "/sell [предмет] [кол-во] — продать N шт\n"
            "/sell all [предмет] — продать все\n\n"
            "Доступные предметы:\n"
            "броня1-5, ружье, гарпун, винтовка, гаусс, аптечка, энергетик, редуктор\n\n"
            "💰 Комиссия: 20%",
            parse_mode='Markdown'
        )
        return
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ /start")
            return
        
        item = context.args[0].lower()
        count = 1
        sell_all = False
        
        if len(context.args) > 1:
            if context.args[1].lower() == 'all':
                sell_all = True
            else:
                try:
                    count = int(context.args[1])
                    if count <= 0:
                        await update.message.reply_text("❌ Положительное число")
                        return
                except ValueError:
                    await update.message.reply_text("❌ Введите число")
                    return
        
        sell_prices = {
            'броня1': 800, 'броня2': 2000, 'броня3': 4000, 'броня4': 8000, 'броня5': 20000,
            'ружье': 240, 'гарпун': 400, 'винтовка': 4000, 'гаусс': 16000,
            'аптечка': 100, 'энергетик': 200, 'редуктор': 1000
        }
        
        if item not in sell_prices:
            await update.message.reply_text(f"❌ Неизвестный предмет: {item}")
            return
        
        available = get_item_count(user, item)
        if available == 0:
            await update.message.reply_text(f"❌ У вас нет {item}")
            return
        
        if sell_all:
            count = available
        elif count > available:
            await update.message.reply_text(f"❌ У вас только {available} шт")
            return
        
        remove_item_from_inventory(user, item, count)
        total = sell_prices[item] * count
        user.radcoins += total
        session.commit()
        
        item_names = {
            'броня1': '🟢 Лёгкая броня', 'броня2': '🔵 Утяжеленная броня',
            'броня3': '🟣 Тактическая броня', 'броня4': '🟠 Тяжёлая броня',
            'броня5': '🔴 Силовая броня',
            'ружье': '🔫 Ружьё', 'гарпун': '🎣 Гарпун', 'винтовка': '🔫 Винтовка',
            'гаусс': '⚡ Винтовка Гаусса', 'аптечка': '💊 Аптечка',
            'энергетик': '⚡ Энергетик', 'редуктор': '⏱️ Редуктор'
        }
        
        await update.message.reply_text(
            f"💰 *Продажа!*\n\n"
            f"📦 {item_names.get(item, item)} x{count}\n"
            f"💵 Получено: +{total} RC\n"
            f"📊 Осталось: {user.radcoins:.0f} RC",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in sell: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== ЭКИПИРОВКА ====================

async def equip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экипировать предметы"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚔️ *Экипировка*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "/equip броня [название] — надеть броню\n"
            "/equip броня 0 — снять броню\n"
            "/equip оружие [название] — надеть оружие\n"
            "/equip оружие 0 — снять оружие\n\n"
            "Доступные предметы:\n"
            "броня1-5, ружье, гарпун, винтовка, гаусс",
            parse_mode='Markdown'
        )
        return
    
    equip_type = context.args[0].lower()
    value = context.args[1].lower()
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ /start")
            return
        
        equipped = get_equipped(user)
        
        armor_names = {
            'броня1': '🟢 Лёгкая броня', 'броня2': '🔵 Утяжеленная броня',
            'броня3': '🟣 Тактическая броня', 'броня4': '🟠 Тяжёлая броня',
            'броня5': '🔴 Силовая броня'
        }
        weapon_names = {
            'ружье': '🔫 Ружьё', 'гарпун': '🎣 Гарпун',
            'винтовка': '🔫 Винтовка', 'гаусс': '⚡ Винтовка Гаусса'
        }
        
        # Броня
        if equip_type == 'броня':
            if value == '0':
                old_armor = equipped.get('armor')
                if old_armor:
                    add_item_to_inventory(user, old_armor, 1)
                    equipped['armor'] = None
                    save_equipped(user, equipped)
                    session.commit()
                    await update.message.reply_text(f"✅ *Снята броня*\n\n{armor_names.get(old_armor, old_armor)} снята", parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ Нет надетой брони")
                return
            
            if value not in armor_names:
                await update.message.reply_text("❌ Доступно: броня1-5")
                return
            
            if get_item_count(user, value) == 0:
                await update.message.reply_text(f"❌ У вас нет {armor_names.get(value, value)}")
                return
            
            old_armor = equipped.get('armor')
            if old_armor:
                add_item_to_inventory(user, old_armor, 1)
            
            remove_item_from_inventory(user, value, 1)
            equipped['armor'] = value
            save_equipped(user, equipped)
            session.commit()
            
            old_text = f"{armor_names.get(old_armor, old_armor)}" if old_armor else "ничего"
            await update.message.reply_text(
                f"✅ *Экипировано!*\n\n"
                f"🛡️ {armor_names.get(value, value)}\n"
                f"📦 Прежнее: {old_text}",
                parse_mode='Markdown'
            )
        
        # Оружие
        elif equip_type == 'оружие':
            if value == '0':
                old_weapon = equipped.get('weapon')
                if old_weapon:
                    add_item_to_inventory(user, old_weapon, 1)
                    equipped['weapon'] = None
                    save_equipped(user, equipped)
                    session.commit()
                    await update.message.reply_text(f"✅ *Снято оружие*\n\n{weapon_names.get(old_weapon, old_weapon)} снято", parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ Нет экипированного оружия")
                return
            
            if value not in weapon_names:
                await update.message.reply_text("❌ Доступно: ружье, гарпун, винтовка, гаусс")
                return
            
            if get_item_count(user, value) == 0:
                await update.message.reply_text(f"❌ У вас нет {weapon_names.get(value, value)}")
                return
            
            old_weapon = equipped.get('weapon')
            if old_weapon:
                add_item_to_inventory(user, old_weapon, 1)
            
            remove_item_from_inventory(user, value, 1)
            equipped['weapon'] = value
            save_equipped(user, equipped)
            session.commit()
            
            old_text = f"{weapon_names.get(old_weapon, old_weapon)}" if old_weapon else "ничего"
            await update.message.reply_text(
                f"✅ *Экипировано!*\n\n"
                f"⚔️ {weapon_names.get(value, value)}\n"
                f"📦 Прежнее: {old_text}",
                parse_mode='Markdown'
            )
        
        else:
            await update.message.reply_text("❌ Используйте: броня, оружие")
    
    except Exception as e:
        logger.error(f"Error in equip: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== КАЗИНО ====================

async def casino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Казино с настраиваемыми шансами"""
    if not context.args:
        await update.message.reply_text(f"🎰 /casino [сумма]\n💰 Ставка от {CASINO_MIN_BET} до {CASINO_MAX_BET} RC")
        return
    
    try:
        bet = int(context.args[0])
        if bet < CASINO_MIN_BET or bet > CASINO_MAX_BET:
            await update.message.reply_text(f"❌ Ставка от {CASINO_MIN_BET} до {CASINO_MAX_BET} RC")
            return
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ /start")
            return
        if user.radcoins < bet:
            await update.message.reply_text(f"❌ Не хватает! У вас {user.radcoins:.0f} RC")
            return
        
        chance = user.casino_chance if user.casino_chance is not None else CASINO_PUBLIC_CHANCE
        mult = user.casino_cash_mult if user.casino_cash_mult is not None else CASINO_PUBLIC_CASH_MULT
        
        user.radcoins -= bet
        
        if random.random() < chance / 100:
            win = bet * mult
            user.radcoins += win
            session.commit()
            await update.message.reply_text(
                f"🎰 *ДЖЕКПОТ!*\n\n"
                f"💰 +{win} RC!\n"
                f"🎲 Шанс: {chance}%\n"
                f"✨ Множитель: x{mult}\n"
                f"📊 Баланс: {user.radcoins:.0f} RC",
                parse_mode='Markdown'
            )
        else:
            session.commit()
            await update.message.reply_text(
                f"💀 *Проигрыш!*\n\n"
                f"📉 -{bet} RC\n"
                f"🎲 Шанс: {chance}%\n"
                f"📊 Баланс: {user.radcoins:.0f} RC",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Error in casino: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== ОБМЕН ====================

async def exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обмен фрагментов на коины (лимит 1 000 000 RF)"""
    if not context.args:
        await update.message.reply_text("💱 /exchange [количество]\n📊 1 RF = 50 RC + бонусы\n⚠️ Лимит: 1 000 000 RF за раз")
        return
    
    try:
        amount = int(context.args[0])
        if amount <= 0:
            await update.message.reply_text("❌ Положительное число")
            return
        if amount > 1000000:
            await update.message.reply_text("❌ Лимит 1 000 000 RF за раз!")
            return
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ /start")
            return
        if user.radfragments < amount:
            await update.message.reply_text(f"❌ Не хватает! У вас {user.radfragments} RF")
            return
        
        if amount >= 100:
            coins = amount * 65 + 1500
        elif amount >= 50:
            coins = amount * 60 + 500
        elif amount >= 10:
            coins = amount * 55 + 50
        else:
            coins = amount * 50
        
        user.radfragments -= amount
        user.radcoins += coins
        session.commit()
        await update.message.reply_text(
            f"💱 *Обмен*\n\n"
            f"📦 {amount} RF → {coins} RC\n"
            f"☢️ Баланс: {user.radcoins:.0f} RC",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in exchange: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== КРАФТ ====================

async def craft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Крафт предметов"""
    if not context.args:
        await update.message.reply_text(
            "🛠️ *Крафт предметов*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "*💊 АПТЕЧКИ*\n"
            "• 💊 Аптечка (25%) — 2 RF\n\n"
            "*🎣 ОРУЖИЕ*\n"
            "• 🎣 Гарпун — 300 RF + 700 RC\n"
            "• 🔫 Винтовка — 250 RF + 3500 RC\n\n"
            "*🥇 БРОНЯ*\n"
            "• 🥈 Броня 2 — 250 RF + 2700 RC\n"
            "• 🥇 Броня 3 — 800 RF + 6700 RC\n\n"
            "📝 */craft [предмет]*",
            parse_mode='Markdown'
        )
        return
    
    item = context.args[0].lower()
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ /start")
            return
        
        recipes = {
            'аптечка': {'rf': 2, 'rc': 0, 'level': 1},
            'гарпун': {'rf': 300, 'rc': 700, 'level': 1},
            'винтовка': {'rf': 250, 'rc': 3500, 'level': 4},
            'броня2': {'rf': 250, 'rc': 2700, 'level': 11},
            'броня3': {'rf': 800, 'rc': 6700, 'level': 21}
        }
        
        if item not in recipes:
            await update.message.reply_text("❌ Неизвестный рецепт")
            return
        
        recipe = recipes[item]
        if user.level < recipe['level']:
            await update.message.reply_text(f"❌ Нужен {recipe['level']} уровень")
            return
        if user.radfragments < recipe['rf']:
            await update.message.reply_text(f"❌ Нужно {recipe['rf']} RF")
            return
        if user.radcoins < recipe['rc']:
            await update.message.reply_text(f"❌ Нужно {recipe['rc']} RC")
            return
        
        user.radfragments -= recipe['rf']
        user.radcoins -= recipe['rc']
        
        if item == 'гарпун':
            add_item_to_inventory(user, 'гарпун', 1)
        elif item == 'винтовка':
            add_item_to_inventory(user, 'винтовка', 1)
        elif item == 'броня2':
            add_item_to_inventory(user, 'броня2', 1)
        elif item == 'броня3':
            add_item_to_inventory(user, 'броня3', 1)
        else:
            add_item_to_inventory(user, 'аптечка', 1)
        
        session.commit()
        await update.message.reply_text(
            f"✅ *Создано: {item}*\n"
            f"💰 Потрачено: {recipe['rf']} RF + {recipe['rc']} RC",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in craft: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== ИСПОЛЬЗОВАНИЕ ПРЕДМЕТОВ ====================

async def use_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Использовать расходный предмет (энергетик или редуктор)"""
    if not context.args:
        await update.message.reply_text(
            "⚡ *Использование предметов*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "/use энергетик [кол-во] — бонусы на 6 часов\n"
            "/use редуктор [кол-во] — ускорение сбора на 3 дня\n\n"
            "📦 Можно использовать несколько штук сразу, эффекты суммируются.",
            parse_mode='Markdown'
        )
        return
    
    item = context.args[0].lower()
    count = 1
    if len(context.args) > 1:
        try:
            count = int(context.args[1])
            if count <= 0 or count > 100:
                await update.message.reply_text("❌ 1-100 штук за раз")
                return
        except ValueError:
            await update.message.reply_text("❌ Введите число")
            return
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ /start")
            return
        
        now = datetime.now()
        
        if item == 'энергетик':
            available = get_item_count(user, 'энергетик')
            if available < count:
                await update.message.reply_text(f"❌ У вас только {available} энергетиков!")
                return
            
            remove_item_from_inventory(user, 'энергетик', count)
            
            if user.energy_drink_until and user.energy_drink_until > now:
                user.energy_drink_until += timedelta(hours=6 * count)
                user.energy_drink_stacks += count
            else:
                user.energy_drink_until = now + timedelta(hours=6 * count)
                user.energy_drink_stacks = count
            
            session.commit()
            
            hours = 6 * count
            await update.message.reply_text(
                f"⚡ *Энергетик активирован!*\n\n"
                f"📦 Использовано: {count} шт\n"
                f"⏰ Длительность: {hours} часов\n"
                f"✨ Бонусы:\n"
                f"  • +10% шанс выжить на охоте\n"
                f"  • +5% к сбору RC\n"
                f"  • +25% к сбору RF\n"
                f"  • +100% к клановым кристаллам\n\n"
                f"📊 Активно до: {user.energy_drink_until.strftime('%d.%m %H:%M')}",
                parse_mode='Markdown'
            )
        
        elif item == 'редуктор':
            available = get_item_count(user, 'редуктор')
            if available < count:
                await update.message.reply_text(f"❌ У вас только {available} редукторов!")
                return
            
            remove_item_from_inventory(user, 'редуктор', count)
            
            if user.cooldown_reducer_until and user.cooldown_reducer_until > now:
                user.cooldown_reducer_until += timedelta(days=3 * count)
                user.reducer_stacks += count
            else:
                user.cooldown_reducer_until = now + timedelta(days=3 * count)
                user.reducer_stacks = count
            
            session.commit()
            
            days = 3 * count
            await update.message.reply_text(
                f"⏱️ *Редуктор активирован!*\n\n"
                f"📦 Использовано: {count} шт\n"
                f"⏰ Длительность: {days} дней\n"
                f"⚡ Эффект: ускорение восстановления сбора вдвое\n\n"
                f"📊 Активно до: {user.cooldown_reducer_until.strftime('%d.%m %H:%M')}",
                parse_mode='Markdown'
            )
        
        else:
            await update.message.reply_text("❌ Доступно: энергетик, редуктор")
    
    except Exception as e:
        logger.error(f"Error in use_item: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()
