# collect.py - Сбор, охота, локации, питомцы
# Версия: 2.0.0

import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

# Импорты из config
from config import logger, MAX_LEVEL, get_random_interval, calculate_reward, calculate_experience, get_exp_for_level

# Импорты из core
from core import send_to_private

# Импорты из database
from database import Session, User, Clan

# Импорты из utils
from utils import get_equipped, get_item_count, add_item_to_inventory, remove_item_from_inventory, apply_class_bonus, calculate_survive_chance, check_achievements


# ==================== СБОР РЕСУРСОВ ====================

async def collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбор ресурсов"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user:
            user = User(user_id=user_id, username=username)
            session.add(user)
            session.commit()
        
        equipped = get_equipped(user)
        now = datetime.now()
        
        if user.next_collection_time and now < user.next_collection_time:
            remaining = user.next_collection_time - now
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            await update.message.reply_text(f"⏰ *Следующий сбор через {hours}ч {minutes}мин.*", parse_mode='Markdown')
            return
        
        actual_level = min(user.level, MAX_LEVEL)
        
        base_rc = calculate_reward(actual_level)
        exp_gain = calculate_experience()
        
        # Бонусы локации (болото удалено)
        location = user.location if hasattr(user, 'location') else 'normal'
        rc_mult = 1
        rf_mult = 1
        exp_mult = 1
        pet_mult = 1
        chest_mult = 1
        location_msg = ""
        
        if location == 'military':
            chest_mult = 3
            rc_mult = 0
            rf_mult = 0
            exp_gain = random.randint(25, 50)
            location_msg = "🏚️ *Военка* — вы обыскиваете ржавые контейнеры в поисках сундуков"
        elif location == 'city':
            rc_mult = 1.5
            rf_mult = 0.5
            location_msg = "🏙️ *Город* — вы бродите по пустынным улицам"
        elif location == 'wasteland':
            rf_mult = 1.5
            rc_mult = 0.7
            location_msg = "🌄 *Пустошь* — вы крадётесь по радиоактивным землям"
        elif location == 'lab':
            exp_mult = 2
            rc_mult = 0.5
            location_msg = "🧪 *Лаба* — вы исследуете заброшенную лабораторию"
        elif location == 'forest':
            pet_mult = 2
            rc_mult = 0.8
            rf_mult = 0
            exp_gain = random.randint(30, 80)
            location_msg = "🌲 *Лес* — вы пробираетесь через густую чащу"
        elif location == 'market':
            rc_mult = 1.2
            rf_mult = 0
            chest_mult = 2
            exp_gain = random.randint(10, 30)
            location_msg = "🎪 *Рынок* — вы бродите между ржавыми прилавками"
        else:
            location_msg = "🌍 *Пустошь* — вы отправляетесь в знакомые места"
        
        # Аномалии
        anomaly_msg = ""
        phase = context.bot_data.get('phase', 1)
        if phase >= 3:
            anomaly_roll = random.random()
            if anomaly_roll < 0.1:
                base_rc = int(base_rc * 1.3)
                anomaly_msg = "\n✨ *Аномалия ДОБЫТЧИК!* Добыча +30%! ✨"
            elif anomaly_roll < 0.2:
                anomaly_msg = "\n🕸️ *Аномалия ЛОВЕЦ!* Кто-то наблюдает... 🕸️"
            elif anomaly_roll < 0.2001:
                reduction = random.randint(1, 5)
                actual_level = max(1, actual_level - reduction)
                anomaly_msg = f"\n🧠 *Аномалия СКЛЕРОЗИК!* Потеряно {reduction} уровней! 🧠"
        
        # Клановый бонус
        clan_bonus = 0
        clan = None
        if user.clan_id:
            clan = session.query(Clan).filter_by(id=user.clan_id).first()
            if clan:
                clan_bonus = clan.collect_bonus
                exp_gain = int(exp_gain * (1 + clan.exp_bonus * 0.05))
        
        rc_gain = int(base_rc * (1 + clan_bonus / 100) * rc_mult)
        exp_gain = int(exp_gain * exp_mult)
        fragment_gain = 0
        
        # Питомцы (алабай и лис удалены)
        if user.pet == 'рысь':
            rc_gain = int(rc_gain * 1.1)
        if user.pet == 'попугай':
            exp_gain = int(exp_gain * 1.4)
        
        # Множители
        multiplier = 1
        double_chance = 9
        if clan:
            double_chance += clan.double_bonus
        if random.random() < 0.01:
            multiplier = 5
            user.crit_collects += 1
        elif random.random() < double_chance / 100:
            multiplier = 2
            user.crit_collects += 1
        rc_gain *= multiplier
        
        # Фрагменты
        fragment_chance = 1
        if user.pet == 'овчарка':
            fragment_chance += 5
        if random.random() < fragment_chance / 100:
            fragment_gain = random.randint(1, 5)
        fragment_gain = int(fragment_gain * rf_mult)
        
        # Бонус класса
        rc_gain, fragment_gain, exp_gain = apply_class_bonus(user, rc_gain, fragment_gain, exp_gain)
        
        # Кристаллы
        crystal_gain = 0
        if clan:
            crystal_gain = random.randint(1, 5)
            if user.pet == 'пума':
                crystal_gain = int(crystal_gain * 1.5)
            clan.treasury_crystals += crystal_gain
        
        # ===== БОНУСЫ ЭНЕРГЕТИКА =====
        if user.energy_drink_until and user.energy_drink_until > now:
            rc_gain = int(rc_gain * 1.05)           # +5% RC
            fragment_gain = int(fragment_gain * 1.25)  # +25% RF
            crystal_gain = int(crystal_gain * 2)       # +100% кристаллы
        # ==============================
        
        user.radcoins += rc_gain
        user.radfragments += fragment_gain
        user.experience += exp_gain
        user.total_collects += 1
        user.total_rc_earned += rc_gain
        if rc_gain > user.best_collect:
            user.best_collect = rc_gain
        
        level_up = False
        while user.level < MAX_LEVEL and user.experience >= get_exp_for_level(user.level + 1):
            user.level += 1
            level_up = True
        
        interval = get_random_interval(user)
        user.last_collection = now
        user.next_collection_time = now + timedelta(minutes=interval)
        
        last_date = user.last_collect_date.date() if user.last_collect_date else None
        today = now.date()
        if last_date == today - timedelta(days=1):
            user.daily_streak += 1
        elif last_date != today:
            user.daily_streak = 1
        user.last_collect_date = now
        
        # Питомец
        pet_encounter = None
        if phase >= 2 and user.level >= 2:
            if random.random() < 0.005 * pet_mult:
                pets = ['овчарка', 'волк', 'рысь', 'пума', 'попугай', 'кайот']
                pet_encounter = random.choice(pets)
        
        new_achievements = check_achievements(user, session)
        
        # Сундуки
        chest_found = None
        if phase >= 2 and chest_mult > 0:
            chest_roll = random.random() * 100
            if chest_roll < 1 * chest_mult:
                user.chest_legendary += 1
                chest_found = "🟠 Легендарный сундук"
            elif chest_roll < 4 * chest_mult:
                user.chest_mythic += 1
                chest_found = "🟡 Мифический сундук"
            elif chest_roll < 8 * chest_mult:
                user.chest_epic += 1
                chest_found = "🟣 Эпический сундук"
            elif chest_roll < 15 * chest_mult:
                user.chest_rare += 1
                chest_found = "🔵 Редкий сундук"
            elif chest_roll < 25 * chest_mult:
                user.chest_common += 1
                chest_found = "🟢 Обычный сундук"
        
        session.commit()
        
        msg = f"🌄 {location_msg}\n\n🔍 Вы находите **{rc_gain}** ☢️ *РадКоинов* и получаете **{exp_gain}** ⚠️ *опыта*!"
        
        if multiplier > 1:
            msg += f"\n✨ *УДАЧА!* Множитель x{multiplier}! ✨"
        if fragment_gain > 0:
            msg += f"\n☣️ *Вам везёт!* +{fragment_gain} РадФрагментов!"
        if crystal_gain > 0:
            msg += f"\n💎 *Клановые кристаллы:* +{crystal_gain} RCr!"
        if level_up:
            msg += f"\n🎉 *УРОВЕНЬ ПОВЫШЕН!* Теперь вы {user.level} уровень! 🎉"
        if anomaly_msg:
            msg += anomaly_msg
        if new_achievements:
            msg += f"\n🏆 *Новые достижения:* {', '.join(new_achievements)}! 🏆"
        
        if user.pet:
            pet_msgs = {
                'овчарка': "🐕 *Овчарка помогает находить ценности!*",
                'волк': "🐺 *Волк предупреждает об опасности!*",
                'рысь': "🐈 *Рысь замечает добычу первой!*",
                'пума': "🐆 *Пума приносит удачу!*",
                'попугай': "🦜 *Попугай ускоряет обучение!*",
                'кайот': "🐕 *Кайот сокращает время до сбора вдвое!*"
            }
            msg += f"\n\n{pet_msgs.get(user.pet, '🐾 *Питомец рядом!*')}"
        
        if pet_encounter:
            msg += f"\n\n🐾 *Вы встречаете {pet_encounter}!*\nИспользуйте `/pet accept` чтобы приручить."
            context.user_data['pending_pet'] = pet_encounter
        
        next_hours = interval // 60
        next_minutes = interval % 60
        msg += f"\n\n⏰ *Следующий сбор через {next_hours}ч {next_minutes}мин.*"
        
        if chest_found:
            msg += f"\n\n🎁 *Вы нашли {chest_found}!* /chest open"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in collect: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка при сборе")
    finally:
        Session.remove()


# ==================== ОХОТА ====================

async def hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Охота на мутантов"""
    user_id = update.effective_user.id
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user:
            await update.message.reply_text("❌ Сначала /start")
            return
        
        if user.level < 2:
            await update.message.reply_text("❌ *Охота доступна со 2 уровня*", parse_mode='Markdown')
            return
        
        phase = context.bot_data.get('phase', 1)
        if phase < 2:
            await update.message.reply_text("❌ *Охота недоступна!* Фаза 2 или 3", parse_mode='Markdown')
            return
        
        now = datetime.now()
        
        cooldown = timedelta(days=1)
        if user.cooldown_reducer_until and user.cooldown_reducer_until > now:
            cooldown = timedelta(hours=12)
        if user.pet == 'кайот':
            cooldown = timedelta(hours=12)
        if (user.cooldown_reducer_until and user.cooldown_reducer_until > now) and user.pet == 'кайот':
            cooldown = timedelta(hours=6)
        
        if user.last_hunt and now - user.last_hunt < cooldown:
            remaining = cooldown - (now - user.last_hunt)
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            await update.message.reply_text(f"⏰ *Следующая охота через {hours}ч {minutes}мин.*", parse_mode='Markdown')
            return
        
        equipped = get_equipped(user)
        
        armor_name = "Нет брони"
        if equipped.get('armor'):
            armor_names = {
                'броня1': '🟢 Лёгкая броня', 'броня2': '🔵 Утяжеленная броня',
                'броня3': '🟣 Тактическая броня', 'броня4': '🟠 Тяжёлая броня',
                'броня5': '🔴 Силовая броня'
            }
            armor_name = armor_names.get(equipped['armor'], "Броня")
        
        weapon_name = "🗡️ Обрез"
        if equipped.get('weapon'):
            weapon_names = {
                'ружье': '🔫 Ружьё', 'гарпун': '🎣 Гарпун',
                'винтовка': '🔫 Винтовка', 'гаусс': '⚡ Винтовка Гаусса'
            }
            weapon_name = weapon_names.get(equipped['weapon'], "🗡️ Обрез")
        
        if equipped.get('weapon') == 'гаусс':
            chances = [40, 25, 20, 15]
        elif equipped.get('weapon') == 'винтовка':
            chances = [50, 30, 15, 5]
        elif equipped.get('weapon') == 'гарпун':
            chances = [70, 20, 9, 1]
        elif equipped.get('weapon') == 'ружье':
            chances = [75, 20, 4, 1]
        else:
            chances = [89, 10, 0.99, 0.01]
        
        roll = random.random() * 100
        if roll < chances[0]:
            reward_rf = 10
            reward_exp = 50
            target_level = 1
            target_name = "🧬 *Мутант 1 уровня*"
            target_desc = "неуклюжее создание с длинными когтями"
        elif roll < chances[0] + chances[1]:
            reward_rf = 30
            reward_exp = 100
            target_level = 2
            target_name = "🧪 *Мутант 2 уровня*"
            target_desc = "крепкий хищник с толстой шкурой"
        elif roll < chances[0] + chances[1] + chances[2]:
            reward_rf = 100
            reward_exp = 250
            target_level = 3
            target_name = "👾 *Мутант 3 уровня*"
            target_desc = "мощный зверь, покрытый костяными наростами"
            user.mutants_lvl3 += 1
        else:
            reward_rf = 1000
            reward_exp = 500
            target_level = 4
            target_name = "👑 *БОСС ПУСТОШИ*"
            target_desc = "легендарное чудовище, внушающее ужас"
            user.bosses_killed += 1
        
        user.mutants_killed += 1
        survived = True
        death_msg = ""
        
        class_name = user.user_class if hasattr(user, 'user_class') else 'stalker'
        if class_name == 'military':
            reward_exp = int(reward_exp * 1.3)
            reward_rf = int(reward_rf * 0.7)
        elif class_name == 'bandit':
            reward_rf = int(reward_rf * 1.4)
            reward_exp = int(reward_exp * 0.75)
        elif class_name == 'scientist':
            reward_exp = int(reward_exp * 1.5)
            reward_rf = int(reward_rf * 1.25)
        
        if target_level >= 3:
            survive_chance = calculate_survive_chance(user, target_level)
            
            # Бонус энергетика к выживанию
            if user.energy_drink_until and user.energy_drink_until > now:
                survive_chance = min(100, survive_chance + 10)
            
            if random.random() * 100 > survive_chance:
                survived = False
                if get_item_count(user, 'аптечка') > 0:
                    remove_item_from_inventory(user, 'аптечка', 1)
                    if random.random() * 100 <= survive_chance:
                        survived = True
                        death_msg = "\n💊 *Аптечка спасла вас!*"
                if not survived:
                    user.deaths += 1
                    equipped = get_equipped(user)
                    if equipped.get('armor'):
                        add_item_to_inventory(user, equipped['armor'], 1)
                    if equipped.get('weapon'):
                        add_item_to_inventory(user, equipped['weapon'], 1)
                    equipped = {'armor': None, 'weapon': None}
                    save_equipped(user, equipped)
                    reward_rf = 0
                    reward_exp = 0
                    death_msg = "\n💀 *ВЫ ПОГИБЛИ!* Снаряжение потеряно..."
        
        if survived:
            user.radfragments += reward_rf
            user.experience += reward_exp
        user.last_hunt = now
        
        check_achievements(user, session)
        session.commit()
        
        if survived:
            hours = cooldown.seconds // 3600
            msg = (
                f"🏹 *Охота в Пустоши*\n\n"
                f"Вы крадётесь с {weapon_name}. {armor_name} защищает вас.\n\n"
                f"Из темноты выпрыгивает {target_name} — {target_desc}!\n\n"
                f"*Вы победили!*\n\n"
                f"💰 *Награда:* +{reward_rf} ☣️ РадФрагментов!\n"
                f"⚠️ *Опыт:* +{reward_exp}!\n"
                f"{death_msg}\n\n"
                f"⏰ *Следующая охота через {hours} часов.*"
            )
        else:
            msg = (
                f"🏹 *Охота в Пустоши*\n\n"
                f"Вы крадётесь с {weapon_name}.\n\n"
                f"*Из темноты выпрыгивает {target_name} — {target_desc}!*\n"
                f"{death_msg}"
            )
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in hunt: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка при охоте")
    finally:
        Session.remove()


# ==================== ЛОКАЦИИ ====================

async def locate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Смена локации"""
    if not context.args:
        session = Session()
        try:
            user = session.query(User).filter_by(user_id=update.effective_user.id).first()
            if not user:
                await update.message.reply_text("❌ /start")
                return
            loc = user.location if hasattr(user, 'location') else 'normal'
            loc_names = {
                'normal': '🌍 Обычная Пустошь',
                'military': '🏚️ Военка',
                'city': '🏙️ Город',
                'wasteland': '🌄 Пустошь',
                'lab': '🧪 Лаба',
                'forest': '🌲 Лес',
                'market': '🎪 Рынок'
            }
            await update.message.reply_text(
                f"🗺️ *Текущая локация:* {loc_names.get(loc, '🌍 Обычная Пустошь')}\n\n"
                f"📌 *Сменить:* `/locate [название]`\n\n"
                f"Доступные локации:\n"
                f"🌍 `normal` — обычная\n"
                f"🏚️ `military` — Военка (сундуки x3)\n"
                f"🏙️ `city` — Город (RC +50%)\n"
                f"🌄 `wasteland` — Пустошь (RF +50%)\n"
                f"🧪 `lab` — Лаба (опыт x2)\n"
                f"🌲 `forest` — Лес (питомцы x2)\n"
                f"🎪 `market` — Рынок (предметы 10%)",
                parse_mode='Markdown'
            )
        finally:
            Session.remove()
        return
    
    loc = context.args[0].lower()
    valid = ['normal', 'military', 'city', 'wasteland', 'lab', 'forest', 'market']
    if loc not in valid:
        await update.message.reply_text("❌ Локации: normal, military, city, wasteland, lab, forest, market")
        return
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ /start")
            return
        user.location = loc
        session.commit()
        loc_names = {
            'normal': '🌍 Обычная Пустошь', 'military': '🏚️ Военка',
            'city': '🏙️ Город', 'wasteland': '🌄 Пустошь',
            'lab': '🧪 Лаба', 'forest': '🌲 Лес', 'market': '🎪 Рынок'
        }
        await update.message.reply_text(f"🗺️ *Локация изменена на {loc_names[loc]}!*", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in locate: {e}")
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


# ==================== ПИТОМЦЫ ====================

async def pet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление питомцами"""
    if not context.args:
        await update.message.reply_text(
            "🐾 *Питомцы Пустоши*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "При сборе есть 0.5% шанс встретить питомца.\n\n"
            "🐕 Овчарка — +5% RF\n"
            "🐺 Волк — +10% выживаемость\n"
            "🐈 Рысь — +10% RC\n"
            "🐆 Пума — +50% кристаллы\n"
            "🦜 Попугай — +40% опыт\n"
            "🐕 Кайот — кулдаун ÷2\n\n"
            "📝 /pet accept — приручить\n"
            "📝 /pet deny — отказаться\n"
            "📝 /pet bye — отпустить",
            parse_mode='Markdown'
        )
        return
    action = context.args[0].lower()
    if action == "accept":
        await pet_accept(update, context)
    elif action == "deny":
        await pet_deny(update, context)
    elif action == "bye":
        await pet_bye(update, context)
    else:
        await update.message.reply_text("❌ accept, deny, bye")

async def pet_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = context.user_data.get('pending_pet')
    if not pending:
        await update.message.reply_text("🐾 *Нет найденного питомца*", parse_mode='Markdown')
        return
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if user:
            if user.pet:
                await update.message.reply_text("❌ *У вас уже есть питомец!*", parse_mode='Markdown')
                return
            user.pet = pending
            session.commit()
            await update.message.reply_text(f"🐾 *Питомец приручён!*\n\n✨ {pending} теперь ваш спутник! ✨", parse_mode='Markdown')
        context.user_data.pop('pending_pet')
    except Exception as e:
        logger.error(f"Error in pet_accept: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()

async def pet_deny(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('pending_pet'):
        context.user_data.pop('pending_pet')
        await update.message.reply_text("🐾 *Питомец убежал*", parse_mode='Markdown')
    else:
        await update.message.reply_text("Нет питомца")

async def pet_bye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user or not user.pet:
            await update.message.reply_text("❌ *У вас нет питомца*", parse_mode='Markdown')
            return
        if not context.user_data.get('confirm_bye'):
            context.user_data['confirm_bye'] = True
            await update.message.reply_text(f"⚠️ *Отпустить {user.pet}?* /pet bye ещё раз", parse_mode='Markdown')
            return
        context.user_data.pop('confirm_bye')
        pet_name = user.pet
        user.pet = None
        session.commit()
        await update.message.reply_text(f"🐾 *{pet_name} отпущен*", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in pet_bye: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()
